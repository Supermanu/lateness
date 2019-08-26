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

from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.views.generic import TemplateView
from django.contrib.auth.models import Group

from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from core.models import TeachingModel
from core.utilities import get_menu
from core.views import BaseModelViewSet

from .models import LatenessSettingsModel, LatenessModel
from .serializers import LatenessSettingsSerializer, LatenessSerializer


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
    #filter_class = LatenessFilter
    ordering_fields = ('datetime_update', 'datetime_creation',)
    username_field = None

    def perform_create(self, serializer):
        lateness = serializer.save()
        #TODO Create lateness after sanction.
        if get_settings().trigger_sanction:
            from dossier_eleve.models import CasEleve, SanctionDecisionDisciplinaire

            sanction = SanctionDecisionDisciplinaire.objects.first()
            today_evening = lateness.datetime_creation.replace(hour=17, minute=0)
            cas = CasEleve.objects.create(matricule=lateness.student, name=lateness.student.display,
                                          demandeur=self.request.user.get_full_name(),
                                          sanction_decision=sanction,
                                          explication_commentaire="Ajout automatique.",
                                          sanction_faite=False,
                                          datetime_sanction=today_evening,
                                          created_by=self.request.user
                                          )
            cas.visible_by_groups.set(Group.objects.all())
            lateness.sanction_id = cas.id
            lateness.save()
    
    def perform_destroy(self, instance):
        if instance.sanction_id:
            from dossier_eleve.models import CasEleve

            CasEleve.objects.get(id=instance.sanction_id).delete()
        super().perform_destroy(instance)

    def get_group_all_access(self):
        return get_settings().all_access.all()
