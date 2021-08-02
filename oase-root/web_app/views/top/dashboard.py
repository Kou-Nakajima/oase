# Copyright 2019 NEC Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


"""
[概要]
  ホームビュー

[引数]


[戻り値]


"""


import json
import datetime
import pytz
import traceback
import calendar

from django.conf import settings
from django.http import HttpResponse
from django.db import connection
from django.db.models import Q

from libs.commonlibs import define as defs
from libs.commonlibs.oase_logger import OaseLogger
from web_app.templatetags.common import get_message
from web_app.models.models import EventsRequest


logger = OaseLogger.get_instance() # ロガー初期化


################################################################
class WidgetData(object):


    def __init__(self, now=None, req=None):
        """
        [メソッド概要]
          コンストラクタ
        """

        if not now:
            now = datetime.datetime.now()

        config_tz = getattr(settings, 'TIME_ZONE', 'UTC')
        local_now = pytz.timezone(config_tz).localize(now)
        utc_now   = pytz.timezone('UTC').localize(now)

        self.now       = now
        self.conf_tz   = config_tz
        self.dt_diff   = local_now - utc_now
        self.hour_diff = ((60*60*24) - self.dt_diff.seconds) % (60*60*24) // (60*60)

        self.request = req


    def convert_datetime_to_date(self, dt):
        """
        [メソッド概要]
          指定の日時を日付に変換する
        [引数]
          dt : datetime : naiveなdatetime
        """

        # 日時から日付(0時0分の日時)に変換
        dt = dt.date()
        dt = datetime.datetime.combine(dt, datetime.time())

        # UTCとの時差を加味した日時に変換
        dt = dt + self.dt_diff

        return dt


    def get_data(self, widget_id, **kwargs):
        """
        [メソッド概要]
          IDに応じたデータを取得
        """

        # Widget別データ取得関数
        DATA_FUNC = {
             2 : self.pie_graph_date_unmatch_data,         # 日次の未知ランキング(円グラフ)
             3 : self.pie_graph_date_matching_data,        # 日時の既知/未知(円グラフ)
            21 : self.stacked_graph_hourly_matching_data,  # 時間帯別の既知/未知数(棒グラフ)
            22 : self.stacked_graph_monthly_matching_data, # 月別の既知/未知数(棒グラフ)
        }

        data = {}

        f = DATA_FUNC[widget_id] if widget_id in DATA_FUNC else None
        if f:
            data = f(widget_id, **kwargs)

        return data


    def pie_graph_date_unmatch_data(self, widget_id, **kwargs):
        """
        [メソッド概要]
          日次の未知ランキングデータ取得(円グラフ用)
        """

        lang = kwargs['language'] if 'language' in kwargs else 'EN'

        data = {
            'id'     : widget_id,
            'usage'  : 'Unknown',
            'data'   : {},
        }

        # 円グラフ用データをDBから取得
        try:
            rset = []
            query = ""
            param_list = []

            # SQLのパラメータを設定
            rule_ids = kwargs['req_rule_ids'] if 'req_rule_ids' in kwargs else [0,]
            count    = kwargs['count'] if 'count' in kwargs else 5
            from_day = self.convert_datetime_to_date(self.now)
            to_day   = self.convert_datetime_to_date(self.now + datetime.timedelta(days=1))

            param_list.append(defs.RULE_UNMATCH)
            param_list.append(from_day)
            param_list.append(to_day)
            param_list.extend(rule_ids)
            param_list.append(defs.PRODUCTION)

            # SQL文を作成
            query = (
                "SELECT count(*),event_info "
                "FROM OASE_T_EVENTS_REQUEST "
                "WHERE status=%s "
                "AND event_to_time>=%s AND event_to_time<%s "
                "AND rule_type_id in (" + ("%s," * len(rule_ids)).strip(',') + ") "
                "AND request_type_id=%s "
                "GROUP BY event_info "
                "ORDER BY count(*) DESC,event_info;"
            )

            query2 = (
                "SELECT count(*) "
                "FROM OASE_T_EVENTS_REQUEST "
                "WHERE status=%s "
                "AND event_to_time>=%s AND event_to_time<%s "
                "AND rule_type_id in (" + ("%s," * len(rule_ids)).strip(',') + ") "
                "AND request_type_id=%s;"
            )

            # SQL発行
            with connection.cursor() as cursor:
                cursor.execute(query, param_list)
                rset = cursor.fetchall()

                cursor.execute(query2, param_list)
                rset2 = cursor.fetchall()


            i = 0
            other_count = 0
            for rs in rset:
                if i >= count:
                    other_count = other_count + rs[0]
                else:
                    i = i + 1
                    unknown = 'unknown' + str(i)
                    list = []
                    list = [unknown, rs[0]]
                    data['data'][rs[1]] = list

            other = get_message('MOSJA10062', lang, showMsgId=False)
            list = ['unknown6', other_count]
            data['data'][other] = list

        except Exception as e:
            logger.logic_log('LOSM00001', traceback.format_exc())

        return data


    def pie_graph_date_matching_data(self, widget_id, **kwargs):
        """
        [メソッド概要]
          日時の既知/未知データ取得(円グラフ用)
        """

        lang = kwargs['language'] if 'language' in kwargs else 'EN'
        rule_ids   = kwargs['req_rule_ids'] if 'req_rule_ids' in kwargs else []
        from_day = self.convert_datetime_to_date(self.now)
        to_day = self.convert_datetime_to_date(self.now + datetime.timedelta(days=1))
        from_day = pytz.timezone('UTC').localize(from_day)
        to_day = pytz.timezone('UTC').localize(to_day)
        previously_count = 0
        unknown_count = 0

        try:
            # 既知事象情報取得
            previously_count = EventsRequest.objects.filter(
                Q(rule_type_id__in=rule_ids),
                Q(request_type_id=1),
                Q(status=3) | Q(status=4),
                Q(event_to_time__gte=from_day),
                Q(event_to_time__lt =to_day),
                ).count()

            # 未知事象
            unknown_count = EventsRequest.objects.filter(
                rule_type_id__in=rule_ids,
                request_type_id=1,
                status=1000,
                event_to_time__gte=from_day,
                event_to_time__lt =to_day,
                ).count()

        except Exception as e:
            logger.logic_log('LOSM00001', traceback.format_exc())

        data = {
            'id'     : widget_id,
            'usage'  : 'Known/Unknown',
            'data'   : [],
        }

        data['data'] = {
            get_message('MOSJA10047', lang, showMsgId=False): ['known1', previously_count],
            get_message('MOSJA10048', lang, showMsgId=False): ['unknown1', unknown_count]
          }

        return data


    def stacked_graph_hourly_matching_data(self, widget_id, **kwargs):
        """
        [メソッド概要]
          時間帯別の既知/未知データ取得(棒グラフ用)
        """

        lang = kwargs['language'] if 'language' in kwargs else 'EN'

        # データの棒グラフ用フォーマットで初期化
        data = {
            'id'     : widget_id,
            'usage'  : [],
            'data'   : [],
        }

        data['usage'] = [
            ['time', get_message('MOSJA10046', lang, showMsgId=False)],
            ['time', get_message('MOSJA10046', lang, showMsgId=False)],
            ['known', get_message('MOSJA10047', lang, showMsgId=False)],
            ['unknown', get_message('MOSJA10048', lang, showMsgId=False)],
        ]

        data['data'] = [
            [get_message('MOSJA10045', lang, showMsgId=False, hour=0),   '0', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=1),   '1', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=2),   '2', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=3),   '3', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=4),   '4', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=5),   '5', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=6),   '6', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=7),   '7', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=8),   '8', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=9),   '9', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=10), '10', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=11), '11', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=12), '12', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=13), '13', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=14), '14', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=15), '15', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=16), '16', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=17), '17', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=18), '18', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=19), '19', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=20), '20', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=21), '21', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=22), '22', 0, 0],
            [get_message('MOSJA10045', lang, showMsgId=False, hour=23), '23', 0, 0]
        ]


        # 棒グラフ用データをDBから取得
        try:
            rset = []
            query = ""
            param_list = []

            # SQLのパラメーターを設定
            date_range = kwargs['date_range']   if 'date_range'   in kwargs else 30
            rule_ids   = kwargs['req_rule_ids'] if 'req_rule_ids' in kwargs else [0,]


            period_to = self.convert_datetime_to_date(self.now)
            period_from = self.convert_datetime_to_date(self.now - datetime.timedelta(days=date_range))

            param_list.append(defs.PROCESSED)
            param_list.append(defs.FORCE_PROCESSED)
            param_list.append(period_from)
            param_list.append(period_to)
            param_list.extend(rule_ids)
            param_list.append(defs.PRODUCTION)

            param_list.append(defs.RULE_UNMATCH)
            param_list.append(period_from)
            param_list.append(period_to)
            param_list.extend(rule_ids)
            param_list.append(defs.PRODUCTION)

            # SQL文を作成
            query = (
                "SELECT t1.hour, IFNULL(known.cnt, 0) cnt, IFNULL(unknown.cnt, 0) uncnt "
                "FROM ("
                "  SELECT 0 hour "
                "  UNION SELECT 1 "
                "  UNION SELECT 2 "
                "  UNION SELECT 3 "
                "  UNION SELECT 4 "
                "  UNION SELECT 5 "
                "  UNION SELECT 6 "
                "  UNION SELECT 7 "
                "  UNION SELECT 8 "
                "  UNION SELECT 9 "
                "  UNION SELECT 10 "
                "  UNION SELECT 11 "
                "  UNION SELECT 12 "
                "  UNION SELECT 13 "
                "  UNION SELECT 14 "
                "  UNION SELECT 15 "
                "  UNION SELECT 16 "
                "  UNION SELECT 17 "
                "  UNION SELECT 18 "
                "  UNION SELECT 19 "
                "  UNION SELECT 20 "
                "  UNION SELECT 21 "
                "  UNION SELECT 22 "
                "  UNION SELECT 23 "
                ") t1 "
                "LEFT OUTER JOIN ("
                "  SELECT DATE_FORMAT(event_to_time, '%%H') hour, COUNT(*) cnt "
                "  FROM OASE_T_EVENTS_REQUEST "
                "  WHERE status in (%s, %s) "
                "  AND event_to_time>=%s AND event_to_time<%s "
                "  AND rule_type_id in (" + ("%s," * len(rule_ids)).strip(',') + ") "
                "  AND request_type_id=%s "
                "  GROUP BY DATE_FORMAT(event_to_time, '%%H') "
                ") known "
                "ON t1.hour=known.hour "
                "LEFT OUTER JOIN ("
                "  SELECT DATE_FORMAT(event_to_time, '%%H') hour, COUNT(*) cnt "
                "  FROM OASE_T_EVENTS_REQUEST "
                "  WHERE status=%s "
                "  AND event_to_time>=%s AND event_to_time<%s "
                "  AND rule_type_id in (" + ("%s," * len(rule_ids)).strip(',') + ") "
                "  AND request_type_id=%s "
                "  GROUP BY DATE_FORMAT(event_to_time, '%%H') "
                ") unknown "
                "ON t1.hour=unknown.hour "
                "ORDER BY t1.hour;"
            )

            # SQL発行
            with connection.cursor() as cursor:
                cursor.execute(query, param_list)
                rset = cursor.fetchall()


            # 取得したデータを棒グラフ用フォーマットに当て込む
            for rs in rset:
                if len(data['data']) <= rs[0]:
                    continue

                # utcとの時差分を加算
                hour = (rs[0] + self.hour_diff) % 24

                data['data'][hour][2] = rs[1]
                data['data'][hour][3] = rs[2]


        except Exception as e:
            logger.logic_log('LOSM00001', traceback.format_exc())


        return data


    def stacked_graph_monthly_matching_data(self, widget_id, **kwargs):
        """
        [メソッド概要]
          月別の既知/未知データ取得(棒グラフ用)
        """

        lang = kwargs['language'] if 'language' in kwargs else 'EN'

        # データの棒グラフ用フォーマットで初期化
        data = {
            'id'     : widget_id,
            'usage'  : [],
            'data'   : [],
        }

        data['usage'] = [
            ['time', get_message('MOSJA10049', lang, showMsgId=False)],
            ['time', get_message('MOSJA10049', lang, showMsgId=False)],
            ['known', get_message('MOSJA10047', lang, showMsgId=False)],
            ['unknown', get_message('MOSJA10048', lang, showMsgId=False)],
        ]

        data['data'] = [
            [get_message('MOSJA10050', lang, showMsgId=False),  '1', 0, 0],
            [get_message('MOSJA10051', lang, showMsgId=False),  '2', 0, 0],
            [get_message('MOSJA10052', lang, showMsgId=False),  '3', 0, 0],
            [get_message('MOSJA10053', lang, showMsgId=False),  '4', 0, 0],
            [get_message('MOSJA10054', lang, showMsgId=False),  '5', 0, 0],
            [get_message('MOSJA10055', lang, showMsgId=False),  '6', 0, 0],
            [get_message('MOSJA10056', lang, showMsgId=False),  '7', 0, 0],
            [get_message('MOSJA10057', lang, showMsgId=False),  '8', 0, 0],
            [get_message('MOSJA10058', lang, showMsgId=False),  '9', 0, 0],
            [get_message('MOSJA10059', lang, showMsgId=False), '10', 0, 0],
            [get_message('MOSJA10060', lang, showMsgId=False), '11', 0, 0],
            [get_message('MOSJA10061', lang, showMsgId=False), '12', 0, 0]
        ]


        # 棒グラフ用データをDBから取得
        try:
            rset = []
            query = ""
            param_list = []

            # SQLのパラメーターを設定
            # うるう年判定
            if calendar.isleap(self.now.year):
                date_range = 365
            else:
                date_range = 364
            rule_ids   = kwargs['req_rule_ids'] if 'req_rule_ids' in kwargs else [0,]

            year = str(self.now.year)
            month = str(self.now.month)
            period_to = year + '-' + month.zfill(2) + '-' + '01' + ' 00:00:00.000000'
            period_to = datetime.datetime.strptime(period_to, '%Y-%m-%d %H:%M:%S.%f')
            period_to = self.convert_datetime_to_date(period_to)
            period_from = self.convert_datetime_to_date(period_to - datetime.timedelta(days=date_range))

            param_list.append(defs.PROCESSED)
            param_list.append(defs.FORCE_PROCESSED)
            param_list.append(period_from)
            param_list.append(period_to)
            param_list.extend(rule_ids)
            param_list.append(defs.PRODUCTION)

            param_list.append(defs.RULE_UNMATCH)
            param_list.append(period_from)
            param_list.append(period_to)
            param_list.extend(rule_ids)
            param_list.append(defs.PRODUCTION)

            # SQL文を作成
            query = (
                "SELECT t1.month, IFNULL(known.cnt, 0) cnt, IFNULL(unknown.cnt, 0) uncnt "
                "FROM ("
                "  SELECT 1 month "
                "  UNION SELECT 2 "
                "  UNION SELECT 3 "
                "  UNION SELECT 4 "
                "  UNION SELECT 5 "
                "  UNION SELECT 6 "
                "  UNION SELECT 7 "
                "  UNION SELECT 8 "
                "  UNION SELECT 9 "
                "  UNION SELECT 10 "
                "  UNION SELECT 11 "
                "  UNION SELECT 12 "
                ") t1 "
                "LEFT OUTER JOIN ("
                "  SELECT DATE_FORMAT(event_to_time, '%%m') month, COUNT(*) cnt "
                "  FROM OASE_T_EVENTS_REQUEST "
                "  WHERE status in (%s, %s) "
                "  AND event_to_time>=%s AND event_to_time<%s "
                "  AND rule_type_id in (" + ("%s," * len(rule_ids)).strip(',') + ") "
                "  AND request_type_id=%s "
                "  GROUP BY DATE_FORMAT(event_to_time, '%%m') "
                ") known "
                "ON t1.month=known.month "
                "LEFT OUTER JOIN ("
                "  SELECT DATE_FORMAT(event_to_time, '%%m') month, COUNT(*) cnt "
                "  FROM OASE_T_EVENTS_REQUEST "
                "  WHERE status=%s "
                "  AND event_to_time>=%s AND event_to_time<%s "
                "  AND rule_type_id in (" + ("%s," * len(rule_ids)).strip(',') + ") "
                "  AND request_type_id=%s "
                "  GROUP BY DATE_FORMAT(event_to_time, '%%m') "
                ") unknown "
                "ON t1.month=unknown.month "
                "ORDER BY t1.month;"
            )

            # SQL発行
            with connection.cursor() as cursor:
                cursor.execute(query, param_list)
                rset = cursor.fetchall()

            # 取得したデータを棒グラフ用フォーマットに当て込む
            for rs in rset:
                if len(data['data']) < rs[0]:
                    continue

                data['data'][rs[0]-1][2] = rs[1]
                data['data'][rs[0]-1][3] = rs[2]


        except Exception as e:
            logger.logic_log('LOSM00001', traceback.format_exc())


        return data



################################################################
def data(request, widget_id):
    """
    [メソッド概要]
      DashBoard画面グラフデータ取得
    """

    logger.logic_log('LOSI00001', 'None', request=request)

    resp_data = {}

    param_info = {
        'language'     : request.user.get_lang_mode(),
        'date_range'   : 30,
        'req_rule_ids' : request.user_config.get_rule_auth_type(2141001008)[defs.VIEW_ONLY] \
                       + request.user_config.get_rule_auth_type(2141001008)[defs.ALLOWED_MENTENANCE],
        'count'        : 5,
    }

    wd = WidgetData()
    resp_data = wd.get_data(widget_id, **param_info)

    logger.logic_log('LOSI00002', resp_data, request=request)

    resp_data = json.dumps(resp_data, ensure_ascii=False)
    return HttpResponse(resp_data)


