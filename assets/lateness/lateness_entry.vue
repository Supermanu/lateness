<!-- This file is part of Happyschool. -->
<!--  -->
<!-- Happyschool is the legal property of its developers, whose names -->
<!-- can be found in the AUTHORS file distributed with this source -->
<!-- distribution. -->
<!--  -->
<!-- Happyschool is free software: you can redistribute it and/or modify -->
<!-- it under the terms of the GNU Affero General Public License as published by -->
<!-- the Free Software Foundation, either version 3 of the License, or -->
<!-- (at your option) any later version. -->
<!--  -->
<!-- Happyschool is distributed in the hope that it will be useful, -->
<!-- but WITHOUT ANY WARRANTY; without even the implied warranty of -->
<!-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the -->
<!-- GNU Affero General Public License for more details. -->
<!--  -->
<!-- You should have received a copy of the GNU Affero General Public License -->
<!-- along with Happyschool.  If not, see <http://www.gnu.org/licenses/>. -->

<template>
    <div>
        <b-card @click="displayPhoto">
            <b-row>
                <b-col cols="2" v-if="showPhoto">
                    <b-img :src="`/static/photos/${lateness.student_id}.jpg`" fluid alt="Responsive image"></b-img>
                </b-col>
                <b-col>
                    <icon v-if="lateness.sanction_id" name="exclamation-circle" class="align-text-bottom"></icon>
                    <strong>{{ niceDate }}</strong>:
                    <a :href='`/annuaire/#/person/student/${lateness.student.matricule}/`'>
                        {{ lateness.student.display }}
                    </a>
                    <b-badge  v-b-tooltip.hover title="Nombre de retards">{{ lateness.lateness_count }}</b-badge>
                </b-col>
                <b-col sm="2">
                    <div class="text-right">
                        <b-btn variant="light" size="sm" @click="$emit('delete')"
                        class="card-link"><icon scale="1.3" name="trash" color="red" class="align-text-bottom"></icon></b-btn>
                    </div>
                </b-col>
            </b-row>
        </b-card>
    </div>
</template>

<script>
import Vue from 'vue';

import Moment from 'moment';
Moment.locale('fr');

import 'vue-awesome/icons'
import Icon from 'vue-awesome/components/Icon.vue'
Vue.component('icon', Icon);

export default {
    props: ["lateness"],
    data: function () {
        return {
            showPhoto: false,
        }
    },
    computed: {
        niceDate: function () {
            return Moment(this.lateness.datetime_creation).format('HH:mm DD/MM');
        }
    },
    methods: {
        displayPhoto: function () {
            this.showPhoto = true;
            setTimeout(() => {
                this.showPhoto = false;
            }, 5000);
        }
    },
}
</script>
