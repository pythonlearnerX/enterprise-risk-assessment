"""risk_project 初始化：把 PyMySQL 注册为 MySQLdb，Django 启动即生效。"""
import pymysql

pymysql.install_as_MySQLdb()