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
  Exastro連携メイン処理
"""


import os
import sys
import traceback
import django
import datetime


# OASE モジュール importパス追加
my_path       = os.path.dirname(os.path.abspath(__file__))
tmp_path      = my_path.split('oase-root')
root_dir_path = tmp_path[0] + 'oase-root'
sys.path.append(root_dir_path)

# OASE モジュール import
# #LOCAL_PATCH#
os.environ['DJANGO_SETTINGS_MODULE'] = 'confs.frameworkconfs.settings'
django.setup()

from django.conf import settings
from django.db import transaction

#################################################
# デバック用
if settings.DEBUG and getattr(settings, 'ENABLE_NOSERVICE_BACKYARDS', False):
    oase_root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..')
    os.environ['OASE_ROOT_DIR'] = oase_root_dir 
    os.environ['RUN_INTERVAL']  = '3600'
    os.environ['PYTHON_MODULE'] = '/usr/bin/python3'
    os.environ['LOG_LEVEL']     = "TRACE"
    os.environ['LOG_DIR']       = oase_root_dir + "/logs/backyardlogs/exastro_collaboration/"
#################################################

# 環境変数取得
try:
    root_dir_path = os.environ['OASE_ROOT_DIR']
    run_interval  = '3600' # os.environ['RUN_INTERVAL']
    python_module = os.environ['PYTHON_MODULE']
    log_dir       = os.environ['LOG_DIR']
    log_level     = os.environ['LOG_LEVEL']
except Exception as e:
    print(str(e))
    sys.exit(2)

# ロガー初期化
from libs.commonlibs.oase_logger import OaseLogger
logger = OaseLogger.get_instance()

from libs.backyardlibs.oase_action_common_libs import ConstantModules as Cstobj
from libs.backyardlibs.action_driver.ITA.ITA_core import ITA1Core
from libs.commonlibs import define as defs
from libs.commonlibs.aes_cipher import AESCipher
from web_app.models.ITA_models import ItaMenuName, ItaParameterItemInfo


class ITAParameterSheetMenuManager:
    """
    [クラス概要]
        ITAパラメーターシートメニュー管理クラス
    """

    def __init__(self, drv_info, user_name, now=None):
        """
        [概要]
        コンストラクタ
        [引数]
        drv_info : dict : ITAアクション設定
        """

        cipher = AESCipher(settings.AES_KEY)

        self.now = now if now else datetime.datetime.now()
        self.user_name = user_name
        self.drv_id = drv_info['ita_driver_id']
        self.ita_config = {}
        self.ita_config['Protocol'] = drv_info['protocol']
        self.ita_config['Host'] = drv_info['hostname']
        self.ita_config['PortNo'] = drv_info['port']
        self.ita_config['user'] = drv_info['username']
        self.ita_config['password'] = cipher.decrypt(drv_info['password'])
        self.ita_config['menuID'] = ''
        self.ita_core = ITA1Core('TOS_Backyard_ParameterSheetMenuManager', 0, 0, 0, 0)

    def get_menu_list(self):
        """
        [概要]
        パラメーターシートメニューの情報リストを取得
        [戻り値]
        flg       : bool : True=成功、False=失敗
        ret_info  : list : パラメーターシートメニューの情報リスト
        """

        logger.logic_log(
            'LOSI00001',
            'Start ITAParameterSheetMenuManager.get_menu_list. DriverID=%s' % (self.drv_id)
        )

        # メニュー作成情報取得
        self.ita_config['menuID'] = '2100160001'
        flg, menu_list = self.ita_core.select_create_menu_info_list(
            self.ita_config,
            ['1', '3',]
        )

        logger.logic_log('LOSI28004', 'create_menu_info', flg, self.drv_id, len(menu_list))

        # メニュー作成情報取得エラー
        if not flg:
            return False, []

        logger.logic_log(
            'LOSI00002',
            'End ITAParameterSheetMenuManager.get_menu_list. DriverID=%s, result=%s, count=%s' % (
                self.drv_id, flg, len(menu_list)
            )
        )

        return flg, menu_list


    def get_hostgroup_flg(self, param_menu_list):
        """
        [概要]
        ホストグループフラグ情報を取得
        [引数]
        param_menu_list : list : パラメーターシートメニューの情報リスト
        [戻り値]
        flg       : bool : True=成功、False=失敗
        ret_info  : dict : パラメーターシートメニューの情報リスト、ホストグループフラグ情報、メニュー項目リスト
        """

        ret_info = {
            'menu_list' : [],
            'use_info'  : {},
        }

        logger.logic_log(
            'LOSI00001',
            'Start ITAParameterSheetMenuManager.get_hostgroup_flg. DriverID=%s' % (self.drv_id)
        )

        # 取得件数0件
        if len(param_menu_list) <= 0:
            return True, ret_info

        # メニュー管理取得用の条件を作成
        menu_names = []
        group_names = []
        use_info = {}
        for menu in param_menu_list:
            menu_name = ''
            group_name = ''
            hostgroup_flg = 0
            vertical_flg = False
            priority = 0

            if menu[Cstobj.FCMI_MENU_NAME]:
                menu_name = menu[Cstobj.FCMI_MENU_NAME]

            if menu[Cstobj.FCMI_USE] in ['ホストグループ用', 'For HostGroup']:
                hostgroup_flg = 1

            elif menu[Cstobj.FCMI_USE] == '':
                hostgroup_flg = -1

            if menu[Cstobj.FCMI_MENUGROUP_FOR_VERTICAL]:
                group_name = menu[Cstobj.FCMI_MENUGROUP_FOR_VERTICAL]
                vertical_flg = True
                priority = 3

            elif menu[Cstobj.FCMI_MENUGROUP_FOR_HOSTGROUP]:
                group_name = menu[Cstobj.FCMI_MENUGROUP_FOR_HOSTGROUP]
                priority = 2

            elif menu[Cstobj.FCMI_MENUGROUP_FOR_HOST]:
                group_name = menu[Cstobj.FCMI_MENUGROUP_FOR_HOST]
                priority = 1

            if menu_name and group_name:
                menu_names.append(menu_name)
                group_names.append(group_name)
                use_info[(group_name, menu_name)] = {
                    'hostgroup_flg' : hostgroup_flg,
                    'vertical_flg' : vertical_flg,
                    'priority' : priority,
                }

        # メニュー管理取得
        self.ita_config['menuID'] = '2100000205'
        flg, menu_list = self.ita_core.select_menu_list(
            self.ita_config,
            menu_names=menu_names,
            group_names=group_names,
            range_start=1,
            range_end=2000000000
        )

        logger.logic_log('LOSI28004', 'menu', flg, self.drv_id, len(menu_list))

        # メニュー管理取得エラー
        if not flg:
            return False, ret_info

        logger.logic_log(
            'LOSI00002',
            'End ITAParameterSheetMenuManager.get_hostgroup_flg. DriverID=%s, result=%s, count=%s' % (
                self.drv_id, flg, len(menu_list)
            )
        )

        ret_info['menu_list'] = menu_list
        ret_info['use_info'] = use_info
        return flg, ret_info

    def get_menu_item_list(self, ret_info):
        """
        [概要]
        メニュー項目リストを取得
        [引数]
        ret_info  : list : メニュー管理の情報リスト
        [戻り値]
        flg       : bool : True=成功、False=失敗
        ret_info  : dict : メニュー項目リスト
        """

        menu_info = {}
        menu_list = []
        if 'menu_list' in ret_info:
            menu_list = ret_info['menu_list']

        use_info = {}
        if 'use_info' in ret_info:
            use_info = ret_info['use_info']

        logger.logic_log(
            'LOSI00001',
            'Start ITAParameterSheetMenuManager.get_menu_item_list. DriverID=%s' % (self.drv_id)
        )


        # メニューIDとメニュー名の紐づけ情報を作成
        menu_names = []
        for menu in menu_list:
            menu_id = int(menu[Cstobj.AML_MENU_ID])
            menu_name = menu[Cstobj.AML_MENU_NAME]
            group_name = menu[Cstobj.AML_MENU_GROUP_NAME]
            group_menu_tpl = (group_name, menu_name)

            if menu_name not in menu_info:
                menu_info[menu_name] = {'menu_id':0, 'priority':0}

            for k, v in use_info.items():
                if k[1] != menu_name:
                    continue

                if v['priority'] > menu_info[menu_name]['priority']:
                    menu_info[menu_name]['menu_id'] = menu_id
                    menu_info[menu_name]['priority'] = v['priority']

            menu_names.append(menu_name)

        # メニュー項目作成情報取得
        self.ita_config['menuID'] = '2100160002'
        flg, item_list = self.ita_core.select_create_item_list(
            self.ita_config,
            #menu_names
        )
        logger.logic_log('LOSI28004', 'create_item_list', flg, self.drv_id, len(item_list))

        # メニュー項目作成情報取得エラー
        if not flg:
            return False, ret_info

        ret_info['item_list'] = item_list
        ret_info['menu_info'] = menu_info

        logger.logic_log(
            'LOSI00002',
            'End ITAParameterSheetMenuManager.get_menu_item_list. DriverID=%s, result=%s, count=%s' % (
                self.drv_id, flg, len(item_list)
            )
        )

        return flg, ret_info

    def save_menu_info(self, menu_info):
        """
        [概要]
        パラメーターシートメニューの情報を保存
        ※try句内で呼び出すこと
        """

        logger.logic_log(
            'LOSI00001',
            'Start ITAParameterSheetMenuManager.save_menu_info. DriverID=%s' % (self.drv_id)
        )

        menu_list = []
        use_info  = {}
        if 'menu_list' in menu_info:
            menu_list = menu_info['menu_list']

        if 'use_info' in menu_info:
            use_info = menu_info['use_info']

        # ITAから取得したメニュー情報を作成
        ita_data = {}
        ita_set = set()
        for menu in menu_list:
            group_id = int(menu[Cstobj.AML_MENU_GROUP_ID])
            menu_id = int(menu[Cstobj.AML_MENU_ID])
            group_name = menu[Cstobj.AML_MENU_GROUP_NAME]
            menu_name = menu[Cstobj.AML_MENU_NAME]

            group_menu_tpl = (group_id, menu_id)
            ita_set.add(group_menu_tpl)
            ita_data[group_menu_tpl] = {
                'group_name' : group_name,
                'menu_name' : menu_name,
            }

        logger.logic_log('LOSI28002', 'ITA', self.drv_id, len(ita_set))

        # OASEが保持しているメニュー情報を作成
        oase_data = {}
        oase_set = set()
        rset = ItaMenuName.objects.select_for_update().filter(ita_driver_id=self.drv_id)
        rset = rset.values('ita_menu_name_id', 'menu_group_id', 'menu_id')
        for rs in rset:
            group_menu_tpl = (rs['menu_group_id'], rs['menu_id'])
            oase_set.add(group_menu_tpl)
            oase_data[group_menu_tpl] = rs['ita_menu_name_id']

        logger.logic_log('LOSI28002', 'OASE', self.drv_id, len(oase_set))

        # OASEには存在する／ITAには存在しない情報は削除
        del_ids = []
        del_set = oase_set - ita_set
        for d in del_set:
            if d in oase_data:
                del_ids.append(oase_data[d])

        if len(del_ids) > 0:
            ItaMenuName.objects.filter(ita_menu_name_id__in=del_ids).delete()

        logger.logic_log('LOSI28003', 'Delete', self.drv_id, len(del_ids))

        # OASEにも存在する／ITAにも存在する情報は更新
        upd_set = oase_set & ita_set
        for u in upd_set:
            if u not in oase_data or u not in ita_data:
                continue

            pkey = oase_data[u]
            group_name = ita_data[u]['group_name']
            menu_name = ita_data[u]['menu_name']
            hg_flag = use_info[(group_name, menu_name)]['hostgroup_flg'] if (group_name, menu_name) in use_info else 0
            ItaMenuName.objects.filter(ita_menu_name_id=pkey).update(
                menu_group_name = group_name,
                menu_name = menu_name,
                hostgroup_flag = hg_flag,
                last_update_timestamp = self.now,
                last_update_user = self.user_name
            )

        logger.logic_log('LOSI28003', 'Update', self.drv_id, len(upd_set))

        # OASEには存在しない／ITAには存在する情報は挿入
        reg_list = []
        reg_set = ita_set - oase_set
        for r in reg_set:
            group_name = ita_data[r]['group_name']
            menu_name = ita_data[r]['menu_name']
            hg_flag = use_info[(group_name, menu_name)]['hostgroup_flg'] if (group_name, menu_name) in use_info else 0
            reg_list.append(
                ItaMenuName(
                    ita_driver_id = self.drv_id,
                    menu_group_id = r[0],
                    menu_id = r[1],
                    menu_group_name = ita_data[r]['group_name'],
                    menu_name = ita_data[r]['menu_name'],
                    hostgroup_flag = hg_flag,
                    last_update_timestamp = self.now,
                    last_update_user = self.user_name
                )
            )

        if len(reg_list) > 0:
            ItaMenuName.objects.bulk_create(reg_list)

        logger.logic_log('LOSI28003', 'Insert', self.drv_id, len(reg_list))

        logger.logic_log(
            'LOSI00002',
            'End ITAParameterSheetMenuManager.save_menu_info. DriverID=%s' % (self.drv_id)
        )


    def save_menu_item_info(self, item_info):
        """
        [概要]
        パラメーターシートメニューの項目情報を保存
        ※try句内で呼び出すこと
        """

        logger.logic_log(
            'LOSI00001',
            'Start ITAParameterSheetMenuManager.save_menu_item_info. DriverID=%s' % (self.drv_id)
        )


        item_list = []
        menu_info  = {}
        if 'item_list' in item_info:
            item_list = item_info['item_list']

        if 'menu_info' in item_info:
            menu_info = item_info['menu_info']

        # ITAから取得したメニュー情報を作成
        ita_data = {}
        ita_set = set()
        for item in item_list:
            if item[Cstobj.DALVA_MENU_NAME] not in menu_info:
                continue

            if menu_info[item[Cstobj.DALVA_MENU_NAME]]['menu_id'] == 0:
                continue

            menu_id = menu_info[item[Cstobj.DALVA_MENU_NAME]]['menu_id']
            column_group = item[Cstobj.DALVA_COLUMN_GROUP][:512]
            item_name = item[Cstobj.DALVA_ITEM_NAME]
            item_number = int(item[Cstobj.DALVA_ID])
            ita_order = int(item[Cstobj.DALVA_ITEM_ORDER])

            ita_set.add(item_number)
            ita_data[item_number] = {
                'menu_id' : menu_id,
                'column_group' : column_group,
                'item_name' : item_name,
                'ita_order' : ita_order,
            }

        logger.logic_log('LOSI28002', 'ITA', self.drv_id, len(ita_set))

        # OASEが保持しているメニュー情報を作成
        oase_data = {}
        oase_set = set()
        rset = ItaParameterItemInfo.objects.select_for_update().filter(ita_driver_id=self.drv_id)
        rset = rset.values('ita_parameter_item_info_id', 'item_number')
        for rs in rset:
            oase_set.add(rs['item_number'])
            oase_data[rs['item_number']] = rs['ita_parameter_item_info_id']

        logger.logic_log('LOSI28002', 'OASE', self.drv_id, len(oase_set))

        # OASEには存在する／ITAには存在しない情報は削除
        del_ids = []
        del_set = oase_set - ita_set
        for d in del_set:
            if d in oase_data:
                del_ids.append(oase_data[d])

        if len(del_ids) > 0:
            ItaParameterItemInfo.objects.filter(ita_parameter_item_info_id__in=del_ids).delete()

        logger.logic_log('LOSI28003', 'Delete', self.drv_id, len(del_ids))

        # OASEにも存在する／ITAにも存在する情報は更新
        upd_set = oase_set & ita_set
        for u in upd_set:
            if u not in oase_data or u not in ita_data:
                continue

            pkey = oase_data[u]
            menu_id = ita_data[u]['menu_id']
            column_group = ita_data[u]['column_group']
            item_name = ita_data[u]['item_name']
            ita_order = ita_data[u]['ita_order']

            ItaParameterItemInfo.objects.filter(ita_parameter_item_info_id=pkey).update(
                menu_id = menu_id,
                column_group = column_group,
                item_name = item_name,
                ita_order = ita_order,
                last_update_timestamp = self.now,
                last_update_user = self.user_name
            )

        logger.logic_log('LOSI28003', 'Update', self.drv_id, len(upd_set))

        # OASEには存在しない／ITAには存在する情報は挿入
        reg_list = []
        reg_set = ita_set - oase_set
        for r in reg_set:
            menu_id = ita_data[r]['menu_id']
            column_group = ita_data[r]['column_group']
            item_name = ita_data[r]['item_name']
            item_number = r
            ita_order = ita_data[r]['ita_order']

            reg_list.append(
                ItaParameterItemInfo(
                    ita_driver_id = self.drv_id,
                    menu_id = menu_id,
                    column_group = column_group,
                    item_name = item_name,
                    item_number = item_number,
                    ita_order = ita_order,
                    last_update_timestamp = self.now,
                    last_update_user = self.user_name
                )
            )

        if len(reg_list) > 0:
            ItaParameterItemInfo.objects.bulk_create(reg_list)

        logger.logic_log('LOSI28003', 'Insert', self.drv_id, len(reg_list))

        logger.logic_log(
            'LOSI00002',
            'End ITAParameterSheetMenuManager.save_menu_item_info. DriverID=%s' % (self.drv_id)
        )


    def execute(self):
        """
        [概要]
        ITAからパラメーターシートメニューの情報を取得して保存
        """

        logger.logic_log(
            'LOSI00001',
            'Start ITAParameterSheetMenuManager.execute. DriverID=%s' % (self.drv_id)
        )

        try:
            # パラメーターシートのメニュー作成情報を取得
            flg, menu_list = self.get_menu_list()
            if not flg:
                return

            # メニュー作成情報からメニュー管理情報を取得
            flg, ret_info = self.get_hostgroup_flg(menu_list)
            if not flg:
                return

            # メニュー管理情報を保存
            with transaction.atomic():
                self.save_menu_info(ret_info)

            # メニュー管理情報からメニュー項目作成情報を取得
            flg, ret_info = self.get_menu_item_list(ret_info)
            if not flg:
                return

            # メニュー項目作成情報を保存
            with transaction.atomic():
                self.save_menu_item_info(ret_info)

        except Exception as e:
            logger.system_log('LOSM28001', 'execute')
            logger.logic_log('LOSM00001', 'e: %s, Traceback: %s' % (e, traceback.format_exc()))

        logger.logic_log(
            'LOSI00002',
            'End ITAParameterSheetMenuManager.execute. DriverID=%s' % (self.drv_id)
        )


