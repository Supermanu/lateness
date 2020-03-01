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

from datetime import date

from django.db import models
from django.contrib.auth.models import User, Group

from core.models import StudentModel, TeachingModel


class LatenessSettingsModel(models.Model):
    teachings = models.ManyToManyField(TeachingModel, default=None)
    all_access = models.ManyToManyField(Group, default=None, blank=True)
    trigger_sanction = models.BooleanField(default=False)
    printer = models.CharField(max_length=200, blank=True)
    date_count_start = models.DateField(default=date(year=2019, month=9, day=1))


class LatenessModel(models.Model):
    student = models.ForeignKey(StudentModel, on_delete=models.SET_NULL, null=True)
    sanction_id = models.PositiveIntegerField(null=True, blank=True)
    justified = models.BooleanField(default=False)
    datetime_creation = models.DateTimeField("Date et heure de création du retard",
                                             auto_now_add=True)
    datetime_update = models.DateTimeField("Date et heure de mise à jour du retard",
                                           auto_now=True)

    @property
    def lateness_count(self):
        settings = LatenessSettingsModel.objects.first()
        return LatenessModel.objects.filter(
            student=self.student,
            justified=False,
            datetime_creation__gte=settings.date_count_start).count()
