DROP DATABASE IF EXISTS testdb;
CREATE DATABASE IF NOT EXISTS testdb;
USE testdb;

CREATE TABLE IF NOT EXISTS test (
    test VARCHAR(50) NOT NULL
);
# DROP DATABASE fastapi;
# create database if not exists fastapi;
#
# USE fastapi;
#
# CREATE TABLE IF NOT EXISTS TEST
# (
#     TITLE VARCHAR(50) NOT NULL,
#     GENRE VARCHAR(30) NOT NULL,
#     AGE   INT         NOT NULL,
#     PRIMARY KEY (TITLE)
# )
#
#
# INSERT INTO TEST (TITLE, GENRE, AGE) VALUES ("FOREST GUMP", "DRAMA", 1994);

# create table if not  exists ad_group
# (
#     ad_group_id          varchar(128)  not null comment '광고 그룹 아이디',
#     ad_group_name        varchar(1024) not null comment '광고 그룹명',
#     start_time           datetime      null comment '시작일시',
#     end_time             datetime      null comment '종료일시',
#     ad_network_type      varchar(32)   null comment '지면 플랫폼 정보(유트브/검색/앱/페이스북/인스타/배너)',
#     status               varchar(32)   null comment '상태 (시작/중지/유효/삭제/일시정지/보관...)',
#     campaign_id          varchar(128)  not null comment '캠페인 아이디',
#     media_id             varchar(12)   not null comment '미디어 아이디 ( 구글, 페이스북....)',
#     custom_id            varchar(32)   null comment '광고계정',
#     master_id            varchar(32)   null comment '마스터 아이디',
#     objective            varchar(32)   null comment '목표(애드그룹 타입 : 동영상 / 배너 / 검색 )',
#     initial_collect_date date          null comment '최초 수집일',
#     last_collect_date    date          null comment '최종 수집일',
#     primary key (ad_group_id, campaign_id, media_id)
# );