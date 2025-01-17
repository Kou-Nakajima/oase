#!/bin/bash
#   Copyright 2019 NEC Corporation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
############################################################
#
# 【概要】
#    init_custom.yaml作成ツール
#
############################################################

################################################################################
# generic functions(should have no dependencies on global variables)

check_result() {
    if [ $1 -ne 0 ]; then
        log "ERROR : $2."
        exit 1
    fi
}

################################################################################
# configuration functions

################################################################################
# append to init_custom.yaml
create_initcustom() {

    if [ $# -ne 6 ]; then
        log "ERROR : missing required positional argument."
        exit 1
    fi

    if [ ${oase_language} == 'ja_JP' ]; then
        admin_name='システム管理者'
    else
        admin_name='administrator'
    fi

cat << EOS >> $OASE_INICUSTOM_FILE
- model: web_app.System
  pk: $1
  fields:
    config_name: $2
    category: $3
    config_id: $4
    value: $5
    maintenance_flag: 0
    last_update_timestamp: $6
    last_update_user: ${admin_name}

EOS

}

################################################################################
log "INFO : Start DB existence check."
################################################################################
result=$(env MYSQL_PWD="$db_root_password" mysql -u root -e "show databases" 2>> "$OASE_INSTALL_LOG_FILE")
check_result $? "$result"

db_exists=$(echo "$result" | grep -E ^${db_name}$ 2>> "$OASE_INSTALL_LOG_FILE")

_db_exists_flag=false

if [ -n "$db_exists" ]; then

    ################################################################################
    log "INFO : ${db_name} exists."
    ################################################################################

    _db_exists_flag=true

else

    ################################################################################
    log "INFO : Start CREATE DATABASE."
    ################################################################################

    result=$(env MYSQL_PWD="$db_root_password" mysql -u root -e "CREATE DATABASE ${db_name} CHARACTER SET utf8;" 2>> "$OASE_INSTALL_LOG_FILE")
    check_result $? "$result"

    ################################################################################
    log "INFO : CREATE DATABASE is completed."
    ################################################################################
fi

result=$(env MYSQL_PWD="$db_root_password" mysql -u root -e "SELECT User FROM mysql.user;" 2>> "$OASE_INSTALL_LOG_FILE")
check_result $? "$result"
user_exits=$(echo "$result" | grep -E ^${db_username}$ 2>> "$OASE_INSTALL_LOG_FILE")

if [ -z "$user_exits" ]; then

    ################################################################################
    log "INFO : Start CREATE USER."
    ################################################################################

    #result=$(echo "SET GLOBAL validate_password.length=4;" | mysql -u root -p${db_root_password} 2>> "$OASE_INSTALL_LOG_FILE")
    #result=$(echo "SET GLOBAL validate_password.mixed_case_count=0;" | mysql -u root -p${db_root_password} 2>> "$OASE_INSTALL_LOG_FILE")
    #result=$(echo "SET GLOBAL validate_password.number_count=0;" | mysql -u root -p${db_root_password} 2>> "$OASE_INSTALL_LOG_FILE")
    #result=$(echo "SET GLOBAL validate_password.special_char_count=0;" | mysql -u root -p${db_root_password} 2>> "$OASE_INSTALL_LOG_FILE")
    #result=$(echo "SET GLOBAL validate_password.policy=LOW;" | mysql -u root -p${db_root_password} 2>> "$OASE_INSTALL_LOG_FILE")

    result=$(env MYSQL_PWD="$db_root_password" mysql -u root -e "CREATE USER '"${db_username}"' IDENTIFIED BY '"${db_password}"';" 2>> "$OASE_INSTALL_LOG_FILE")
    check_result $? "$result"

    ################################################################################
    log "INFO : CREATE USER is completed."
    ################################################################################
fi

result=$(env MYSQL_PWD="$db_root_password" mysql -u root -e "GRANT ALL ON "${db_name}".* TO '"${db_username}"';" 2>> "$OASE_INSTALL_LOG_FILE")
check_result $? "$result"

result=$(env MYSQL_PWD="$db_root_password" mysql -u root -e "grant all privileges on *.* to '"${db_username}"'@'localhost' identified by '"${db_password}"' with grant option;" 2>> "$OASE_INSTALL_LOG_FILE")
check_result $? "$result"

################################################################################
log "INFO : DB existence check is completed."
################################################################################

if ${_db_exists_flag}; then
    ################################################################################
    log "INFO : Skip the following because the DB existed."
    ################################################################################
    exit 0
fi

################################################################################
log "INFO : Start create init_custom.yaml."
################################################################################

# get init_costom.yaml
OASE_FIXTURES_DIR=$(cd $oase_directory/OASE/oase-root/web_app/fixtures/;pwd)
OASE_INICUSTOM_FILE=$OASE_FIXTURES_DIR/init_custom.yaml

# initialize init_custom.yaml
if [ -e $OASE_INICUSTOM_FILE ]; then
    log "INFO : Initialize init_custom.yaml."
    cp /dev/null $OASE_INICUSTOM_FILE
fi

# append to init_custom.yaml
log "INFO : append to init_custom.yaml."

# password encryption
encrypter=$oase_directory/OASE/tool/encrypter.py

date=`date +"%Y-%m-%dT%H:%M:%S"`
create_initcustom 2  "ルールファイル設置ルートパス"  "RULE"          "RULEFILE_ROOTPATH" ${rulefile_rootpath}  $date
create_initcustom 26 "DMリクエスト送信先"            "DMSETTINGS"    "DM_IPADDRPORT"     ${rule_engine_ipaddrport}      $date
create_initcustom 27 "DMユーザID"                    "DMSETTINGS"    "DM_USERID"         ${rule_engine_adminname}   $date
encrypted_password=$(python3 $encrypter ${rule_engine_password} 2>> "$OASE_INSTALL_LOG_FILE")
check_result $? $encrypted_password
create_initcustom 28 "DMパスワード"                  "DMSETTINGS"    "DM_PASSWD"         $encrypted_password   $date
create_initcustom 29 "適用君待ち受け情報"            "APPLYSETTINGS" "APPLY_IPADDRPORT"  ${apply_ipaddrport}   $date
create_initcustom 31 "OASEメールSMTP"                "OASE_MAIL"     "OASE_MAIL_SMTP"    ${oasemail_smtp}      $date
create_initcustom 32 "Maven repositoryパス"          "RULE"          "MAVENREP_PATH"     ${mavenrep_path}      $date
create_initcustom 50 "RabbitMQユーザID"              "RABBITMQ"      "MQ_USER_ID"        ${RabbitMQ_username}  $date
encrypted_password=$(python3 $encrypter ${RabbitMQ_password} 2>> "$OASE_INSTALL_LOG_FILE")
check_result $? $encrypted_password
create_initcustom 51 "RabbitMQパスワード"            "RABBITMQ"      "MQ_PASSWORD"       $encrypted_password   $date
create_initcustom 52 "RabbitMQIPアドレス"            "RABBITMQ"      "MQ_IPADDRESS"      ${RabbitMQ_ipaddr}    $date
create_initcustom 53 "RabbitMQキュー名"              "RABBITMQ"      "MQ_QUEUE_NAME"     ${RabbitMQ_queuename} $date

################################################################################
log "INFO : Create init_custom.yaml is completed."
################################################################################

################################################################################
log "INFO : Start create init.yaml."
################################################################################

# get init.yaml
OASE_FIXTURES_DIR=$(cd $oase_directory/OASE/oase-root/web_app/fixtures/;pwd)
OASE_INIT_FILE=$OASE_FIXTURES_DIR/init.yaml

if [ ${oase_language} == 'ja_JP' ]; then
    oase_lang=1
    oase_admin='システム管理者'
    oase_admin_msg='システム管理用の全権限を持つ'
    oase_sso='SSOデフォルトグループ'
    oase_sso_msg='SSOユーザーの初回ログイン時に自動割り当てされるグループ'
    user_name01='アクションドライバープロシージャ'
    user_name02='OASEエージェントプロシージャ'
    user_name03='OASEルール適用プロシージャ'
    user_name04='OASE_AD連携プロシージャ'
    user_name05='ZABBIXアダプタプロシージャ'
    user_name06='OASE_ITA連携プロシージャ'
else
    oase_lang=2
    oase_admin='administrator'
    oase_admin_msg='All rights reserved for system administration.'
    oase_sso='SSODefaultGroup'
    oase_sso_msg='Group automatically assigned to SSO users upon their first login.'
    user_name01='ActionDriverProcedure'
    user_name02='OASEAgentProcedure'
    user_name03='OASERuleApplicationProcedure'
    user_name04='OASEADLinkedProcedure'
    user_name05='OASEAdapterProcedure'
    user_name06='OASEITALinkedProcedure'
fi

sed -i -e '/^    lang_mode_id:/s/1/'${oase_lang}'/g' $OASE_INIT_FILE
sed -i -e '/^    last_update_user:/s/システム管理者/'${oase_admin}'/g' $OASE_INIT_FILE
sed -i -e '/^    user_name:/s/システム管理者/'${oase_admin}'/g' $OASE_INIT_FILE

sed -i -e '/^    group_name:/s/システム管理者/'${oase_admin}'/g' $OASE_INIT_FILE
sed -i -e "/^    summary:/s/システム管理用の全権限を持つ/${oase_admin_msg}/g" $OASE_INIT_FILE
sed -i -e '/^    group_name:/s/SSOデフォルトグループ/'${oase_sso}'/g' $OASE_INIT_FILE
sed -i -e "/^    summary:/s/SSOユーザーの初回ログイン時に自動割り当てされるグループ/${oase_sso_msg}/g" $OASE_INIT_FILE

sed -i -e '/^    user_name:/s/アクションドライバープロシージャ/'${user_name01}'/g' $OASE_INIT_FILE
sed -i -e '/^    user_name:/s/OASEエージェントプロシージャ/'${user_name02}'/g' $OASE_INIT_FILE
sed -i -e '/^    user_name:/s/OASEルール適用プロシージャ/'${user_name03}'/g' $OASE_INIT_FILE
sed -i -e '/^    user_name:/s/OASE_AD連携プロシージャ/'${user_name04}'/g' $OASE_INIT_FILE
sed -i -e '/^    user_name:/s/ZABBIXアダプタプロシージャ/'${user_name05}'/g' $OASE_INIT_FILE
sed -i -e '/^    user_name:/s/OASE_ITA連携プロシージャ/'${user_name06}'/g' $OASE_INIT_FILE

################################################################################
log "INFO : Create init.yaml is completed."
################################################################################

################################################################################
log "INFO : Start DB migrations."
################################################################################
OASE_WEBAPP_DIR=$(cd $oase_directory/OASE/oase-root/web_app/;pwd)

# if the migrations directory does not exist
if [ ! -e "$OASE_WEBAPP_DIR/migrations" ]; then
    log "INFO : create migrations directory."
    mkdir -p $OASE_WEBAPP_DIR/migrations
fi

OASE_MIGRATIONS_DIR=$(cd $OASE_WEBAPP_DIR/migrations;pwd)

# if the __Init__.py does not exist
if [ ! -e $OASE_MIGRATIONS_DIR/__init__.py ]; then
    log "INFO : create __init__.py."
    touch $OASE_MIGRATIONS_DIR/__init__.py
fi

cd $(dirname $OASE_WEBAPP_DIR)
migrate_log=$(python manage.py makemigrations web_app 2>> "$OASE_INSTALL_LOG_FILE")
check_result $? "$migrate_log"

log "INFO : $migrate_log"

migrate_log=$(python manage.py migrate 2>> "$OASE_INSTALL_LOG_FILE")
check_result $? "$migrate_log"

log "INFO : $migrate_log."

OASE_UNIQUE_DELETE_FILE=$OASE_INSTALL_PACKAGE_DIR/SQL/OASE1.2.0.sql
migrate_log=$(env MYSQL_PWD=${db_password} mysql -u ${db_username} ${db_name} -e "source $OASE_UNIQUE_DELETE_FILE" 2>> "$OASE_INSTALL_LOG_FILE")
check_result $? "$migrate_log"

log "INFO : $migrate_log."

migrate_log=$(python manage.py loaddata init init_custom 2>> "$OASE_INSTALL_LOG_FILE")
check_result $? "$migrate_log"

log "INFO : $migrate_log."

cd - > /dev/null 2>&1

################################################################################
log "INFO : DB migrations is completed."
################################################################################
