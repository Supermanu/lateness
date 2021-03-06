# This file is part of HappySchool.
#
# HappySchool is the legal property of its developers, whose names
# can be found in the AUTHORS file distributed with this source
# distribution.
#
# HappySchool is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# HappySchool is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with HappySchool.  If not, see <http://www.gnu.org/licenses/>.

import json
import datetime

from escpos.printer import Network, Dummy
from unidecode import unidecode

from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.views.generic import TemplateView
from django.contrib.auth.models import Group
from django.db.models import ObjectDoesNotExist, Count
from django.utils import timezone
from django.conf import settings

from django_filters import rest_framework as filters

from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from core.models import TeachingModel
from core.utilities import get_menu
from core.views import BaseModelViewSet, BaseFilters
from core.email import get_resp_emails, send_email

from .models import LatenessSettingsModel, LatenessModel, SanctionTriggerModel
from .serializers import LatenessSettingsSerializer, LatenessSerializer


def get_menu_entry(active_app, request):
    if not request.user.has_perm('lateness.view_latenessmodel'):
        return {}
    return {
            "app": "lateness",
            "display": "Retards",
            "url": "/lateness/",
            "active": active_app == "lateness"
    }


def get_settings():
    settings_lateness = LatenessSettingsModel.objects.first()
    if not settings_lateness:
        # Create default settings.
        settings_lateness = LatenessSettingsModel.objects.create()
        if TeachingModel.objects.count() == 1:
            settings_lateness.teachings.add(TeachingModel.objects.first())
        settings_lateness.save()

    return settings_lateness


class LatenessView(LoginRequiredMixin,
                   PermissionRequiredMixin,
                   TemplateView):
    template_name = "lateness/lateness.html"
    permission_required = ('lateness.view_latenessmodel')
    filters = [
        {'value': 'student__display', 'text': 'Nom'},
        {'value': 'student__matricule', 'text': 'Matricule'},
        {'value': 'count_lateness', 'text': 'Nombre de retard'},
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context['menu'] = json.dumps(get_menu(self.request, "lateness"))
        context['filters'] = json.dumps(self.filters)
        context['settings'] = json.dumps((LatenessSettingsSerializer(get_settings()).data))

        return context


class LatenessFilter(BaseFilters):
    student__display = filters.CharFilter(method='people_name_by')
    count_lateness = filters.NumberFilter(method="count_lateness_by")

    class Meta:
        fields_to_filter = [
            'student__matricule',
        ]
        model = LatenessModel
        fields = BaseFilters.Meta.generate_filters(fields_to_filter)
        filter_overrides = BaseFilters.Meta.filter_overrides

    def count_lateness_by(self, queryset, field_name, value):
        date_from = get_settings().date_count_start
        counting = LatenessModel.objects.filter(justified=False, datetime_creation__gte=date_from) \
            .values("student") \
            .annotate(count_lateness=Count("student")) \
            .filter(count_lateness__gte=value).values_list("student", flat=True)
        return LatenessModel.objects.filter(student__in=counting, justified=False)


class LatenessViewSet(BaseModelViewSet):
    queryset = LatenessModel.objects.all()
    serializer_class = LatenessSerializer
    permission_classes = (IsAuthenticated, DjangoModelPermissions,)
    ordering_fields = ('datetime_update', 'datetime_creation',)
    filter_class = LatenessFilter
    username_field = None

    def get_queryset(self):
        return self.queryset.filter(datetime_creation__gte=get_settings().date_count_start)

    def perform_create(self, serializer):
        lateness = serializer.save()
        printing = self.request.query_params.get('print', None)

        lateness_settings = get_settings()

        lateness_count = self.get_queryset().filter(
            student=lateness.student,
            justified=False,
        ).count()

        if lateness_settings.printer and printing:
            try:
                printer = Network(lateness_settings.printer) if not settings.DEBUG else Dummy()
                printer.charcode('USA')
                printer.set(align='CENTER', text_type='B')
                printer.text('RETARD\n')
                printer.set(align='LEFT')
                absence_dt = lateness.datetime_creation.astimezone(timezone.get_default_timezone())

                count_or_justified = "Retard justifié" if lateness.justified else "Nombre de retards: "
                if not lateness.justified:
                    count_or_justified += "%i" % lateness_count

                printer.text('\n%s %s\n%s\n%s\n%s\nBonne journée !' % (
                    unidecode(lateness.student.last_name),
                    unidecode(lateness.student.first_name),
                    lateness.student.classe.compact_str,
                    absence_dt.strftime("%H:%M - %d/%m/%Y"),
                    count_or_justified
                ))
                if settings.DEBUG:
                    print(printer.output)
                printer.cut()
                printer.close()
            except OSError:
                pass

        for trigger in SanctionTriggerModel.objects.filter(
            teaching=lateness.student.teaching,
            year__year=lateness.student.classe.year
        ):
            count_first = trigger.lateness_count_trigger_first
            count_trigger = trigger.lateness_count_trigger
            if lateness_count < count_first or (
                lateness_count > count_first and (lateness_count - count_first) % count_trigger != 0
            ):
                continue

            lateness.has_sanction = True
            if trigger.only_warn:
                lateness.save()
                continue
            from dossier_eleve.models import CasEleve, SanctionDecisionDisciplinaire

            sanction = SanctionDecisionDisciplinaire.objects.get(id=trigger.sanction_id)
            today = datetime.datetime.today()
            day_shift = 6 + trigger.next_week_day
            day = today + datetime.timedelta(days=(day_shift - today.isoweekday()) % (6 + trigger.delay) + 1)
            day.replace(hour=trigger.sanction_time.hour, minute=trigger.sanction_time.minute)
            cas = CasEleve.objects.create(
                matricule=lateness.student, name=lateness.student.display,
                demandeur=self.request.user.get_full_name(),
                sanction_decision=sanction,
                explication_commentaire="Sanction pour cause de retard.",
                sanction_faite=False,
                datetime_sanction=day,
                created_by=self.request.user
            )
            cas.visible_by_groups.set(Group.objects.all())
            lateness.sanction_id = cas.id
            lateness.save()

        if lateness_settings.notify_responsible:
            responsibles = get_resp_emails(lateness.student)
            context = {"lateness": lateness, "lateness_count": lateness_count}
            send_email(
                responsibles,
                "[Retard]%s  %s %s" % (
                    "[Sanction]" if lateness.has_sanction else "",
                    lateness.student.fullname, lateness.student.classe.compact_str
                ),
                "lateness/lateness_email.html",
                context=context
            )

    def remove_sanction(self, instance):
        if instance.sanction_id:
            from dossier_eleve.models import CasEleve

            try:
                CasEleve.objects.get(id=instance.sanction_id).delete()
            except ObjectDoesNotExist:
                pass
            instance.sanction_id = None
            instance.save()

    def perform_destroy(self, instance):
        self.remove_sanction(instance)
        super().perform_destroy(instance)

    def perform_update(self, serializer):
        instance = serializer.save() 
        if instance.sanction_id and instance.justified:
            self.remove_sanction(instance)

    def get_group_all_access(self):
        return get_settings().all_access.all()
