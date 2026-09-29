"""
Point d'entrée du package de configuration Django.

Sur Windows, la compilation de ``mysqlclient`` est souvent problématique.
PyMySQL (déjà présent dans les dépendances) est un client MySQL pur Python
compatible : on l'enregistre ici comme pilote MySQLdb via l'API officielle
``install_as_MySQLdb()``.
"""

import pymysql

pymysql.install_as_MySQLdb()
