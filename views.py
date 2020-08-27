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

from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.views.generic import TemplateView
from django.contrib.auth.models import Group
from django.db.models import ObjectDoesNotExist
from django.utils import timezone
from django.conf import settings

from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from core.models import TeachingModel
from core.utilities import get_menu
from core.views import BaseModelViewSet
from core.email import get_resp_emails, send_email

from .models import LatenessSettingsModel, LatenessModel
from .serializers import LatenessSettingsSerializer, LatenessSerializer


def get_menu_entry(active_app, user):
    if not user.has_perm('lateness.view_latenessmodel'):
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

    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context['menu'] = json.dumps(get_menu(self.request.user, "lateness"))
        context['filters'] = json.dumps(self.filters)
        context['settings'] = json.dumps((LatenessSettingsSerializer(get_settings()).data))

        return context


class LatenessViewSet(BaseModelViewSet):
    queryset = LatenessModel.objects.all()
    serializer_class = LatenessSerializer
    permission_classes = (IsAuthenticated, DjangoModelPermissions,)
    ordering_fields = ('datetime_update', 'datetime_creation',)
    username_field = None

    def get_queryset(self):
        return self.queryset.filter(datetime_creation__gte=get_settings().date_count_start)

    def perform_create(self, serializer):
        lateness = serializer.save()
        printing = self.request.query_params.get('print', None)
        if get_settings().printer and printing:
            try:
                printer = Network(get_settings().printer) if not settings.DEBUG else Dummy()
                printer.charcode('USA')
                printer.set(align='CENTER', text_type='B')
                printer.text('RETARD\n')
                printer.set(align='LEFT')
                absence_dt = lateness.datetime_creation.astimezone(timezone.get_default_timezone())

                count_or_justified = "Retard justifié" if lateness.justified else "Nombre de retards: "
                if not lateness.justified:
                    count_or_justified += "%i" % self.get_queryset().filter(
                        student=lateness.student,
                        justified=False
                    ).count()

                printer.text('\n%s %s\n%s\n%s\n%s\nBonne journée !' % (
                    lateness.student.last_name,
                    lateness.student.first_name,
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

        if get_settings().notify_responsible:
            responsibles = get_resp_emails(lateness.student)
            context = {"lateness": lateness}
            send_email(
                responsibles,
                "[Retard]  %s %s" % (lateness.student.fullname, lateness.student.classe.compact_str),
                "lateness/lateness_email.html",
                context=context
            )

        #TODO Create lateness after sanction.
        if get_settings().trigger_sanction and not lateness.justified:
            if len(self.get_queryset().filter(student=lateness.student, justified=False)) % 3 != 0:
                return
            from dossier_eleve.models import CasEleve, SanctionDecisionDisciplinaire

            #1234 next wednesday.
            #567 next tuesday.
            sanction = SanctionDecisionDisciplinaire.objects.first()
            day = datetime.datetime.today()
            temp_day = 9 if lateness.student.classe.year < 5 else 8
            day += datetime.timedelta(days=(temp_day - day.isoweekday()) % 7 + 1)
            day = day.replace(hour=16, minute=0, second=0)
            cas = CasEleve.objects.create(matricule=lateness.student, name=lateness.student.display,
                                          demandeur=self.request.user.get_full_name(),
                                          sanction_decision=sanction,
                                          explication_commentaire="Ajout automatique.",
                                          sanction_faite=False,
                                          datetime_sanction=day,
                                          created_by=self.request.user
                                          )
            cas.visible_by_groups.set(Group.objects.all())
            lateness.sanction_id = cas.id
            lateness.save()

    def perform_destroy(self, instance):
        if instance.sanction_id:
            from dossier_eleve.models import CasEleve

            try:
                CasEleve.objects.get(id=instance.sanction_id).delete()
            except ObjectDoesNotExist:
                pass
        super().perform_destroy(instance)

    def get_group_all_access(self):
        return get_settings().all_access.all()
