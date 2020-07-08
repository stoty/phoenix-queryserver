# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import unittest

import sqlalchemy as db
from sqlalchemy import text

from . import TEST_DB_AUTHENTICATION, TEST_DB_AVATICA_PASSWORD, TEST_DB_AVATICA_USER, \
    TEST_DB_TRUSTSTORE, TEST_DB_URL

if sys.version_info.major == 3:
    from urllib.parse import urlparse, urlunparse
else:
    from urlparse import urlparse, urlunparse


@unittest.skipIf(TEST_DB_URL is None, "these tests require the PHOENIXDB_TEST_DB_URL environment variable set to a clean database")
class SQLAlchemyTest(unittest.TestCase):

    def test_connection(self):
        engine = self._create_engine()
        # connection = engine.connect()
        metadata = db.MetaData()
        catalog = db.Table('CATALOG', metadata, schema='SYSTEM', autoload=True, autoload_with=engine)
        self.assertIn('TABLE_NAME', catalog.columns.keys())

    def test_textual(self):
        engine = self._create_engine()
        with engine.connect() as connection:
            try:
                connection.execute('drop table if exists ALCHEMY_TEST')
                connection.execute(text('create table ALCHEMY_TEST (id integer primary key)'))
                connection.execute(text('upsert into ALCHEMY_TEST values (42)'))
                # SQLAlchemy autocommit should kick in
                result = connection.execute(text('select * from ALCHEMY_TEST'))
                row = result.fetchone()
                self.assertEqual(row[0], 42)
            finally:
                connection.execute('drop table if exists ALCHEMY_TEST')

    def test_schema_filtering(self):
        engine = self._create_engine()
        with engine.connect() as connection:
            try:
                connection.execute('drop table if exists ALCHEMY_TEST')
                connection.execute('drop table if exists A.ALCHEMY_TEST_A')
                connection.execute('drop table if exists B.ALCHEMY_TEST_B')

                connection.execute(text('create table ALCHEMY_TEST (ID integer primary key)'))
                connection.execute(text('create table A.ALCHEMY_TEST_A (ID_A integer primary key)'))
                connection.execute(text('create table B.ALCHEMY_TEST_B (ID_B integer primary key)'))

                inspector = db.inspect(engine)
                print(inspector.default_schema_name)

                self.assertEqual(inspector.get_schema_names(), [None, 'A', 'B', 'SYSTEM'])

                self.assertEqual(inspector.get_table_names(), ['ALCHEMY_TEST'])
                self.assertEqual(inspector.get_table_names(schema=''), ['ALCHEMY_TEST'])
                self.assertEqual(inspector.get_table_names(schema='A'), ['ALCHEMY_TEST_A'])
                self.assertEqual(inspector.get_table_names(schema='B'), ['ALCHEMY_TEST_B'])

                self.assertEqual(inspector.get_columns('ALCHEMY_TEST').pop()['name'], 'ID')
                self.assertEqual(
                    inspector.get_columns('ALCHEMY_TEST', schema='').pop()['name'], 'ID')
                self.assertEqual(
                    inspector.get_columns('ALCHEMY_TEST_A', schema='A').pop()['name'], 'ID_A')

                self.assertTrue(engine.has_table('ALCHEMY_TEST'))
                self.assertFalse(engine.has_table('ALCHEMY_TEST', schema='A'))
                self.assertTrue(engine.has_table('ALCHEMY_TEST_A', schema='A'))
                self.assertFalse(engine.has_table('ALCHEMY_TEST', schema='A'))
            finally:
                connection.execute('drop table if exists ALCHEMY_TEST')
                connection.execute('drop table if exists A.ALCHEMY_TEST_A')
                connection.execute('drop table if exists B.ALCHEMY_TEST_B')

    def test_reflection(self):
        engine = self._create_engine()
        with engine.connect() as connection:
            try:
                inspector = db.inspect(engine)
                columns_result = inspector.get_columns('DOES_NOT_EXIST')
                self.assertEqual([], columns_result)
                connection.execute('drop table if exists us_population')
                connection.execute(text('''create table if not exists US_POPULATION (
                state CHAR(2) NOT NULL,
                city VARCHAR NOT NULL,
                population BIGINT
                CONSTRAINT my_pk PRIMARY KEY (state, city))'''))
                columns_result = inspector.get_columns('us_population')
                self.assertEqual(len(columns_result), 3)
            finally:
                connection.execute('drop table if exists us_population')

    @unittest.skip("ORM feature not implemented")
    def test_orm(self):
        pass

    def _create_engine(self):
        ''''Massage the properties that we use for the DBAPI tests so that they apply to
        SQLAlchemy'''

        url_parts = urlparse(TEST_DB_URL)

        tls = url_parts.scheme.lower == 'https'

        url_parts = url_parts._replace(scheme='phoenix')

        connect_args = dict()
        if TEST_DB_AUTHENTICATION:
            connect_args.update(authentication=TEST_DB_AUTHENTICATION)
        if TEST_DB_AVATICA_USER:
            connect_args.update(avatica_user=TEST_DB_AVATICA_USER)
        if TEST_DB_AVATICA_PASSWORD:
            connect_args.update(avatica_password=TEST_DB_AVATICA_PASSWORD)
        if TEST_DB_TRUSTSTORE:
            connect_args.update(trustore=TEST_DB_TRUSTSTORE)

        return db.create_engine(urlunparse(url_parts), tls=tls, connect_args=connect_args)