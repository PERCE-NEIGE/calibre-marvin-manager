#!/usr/bin/env python
# coding: utf-8

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

import os, sqlite3, sys
from datetime import datetime

from calibre.devices.usbms.driver import debug_print
from calibre.ebooks.BeautifulSoup import NavigableString
from calibre_plugins.marvin_manager.annotations import Annotation, Annotations
from calibre_plugins.marvin_manager.common_utils import AnnotationStruct
from calibre_plugins.marvin_manager.common_utils import Logger
from calibre_plugins.marvin_manager.config import plugin_prefs

class AnnotationsDB(Logger):
    """
    Handle I/O with SQLite db
    """
    version = 1

    def __init__(self, opts, path):
        self.conn = None
        self.db_version = None
        self.opts = opts
        self.path = path

    def add_to_annotations_db(self, annotations_db, annotation):
        '''
        annotation is a dict containing the metadata describing the annotation:
         book_id - unique per book for the reader app
         annotation_id
         epubcfi
         highlight_text
         note_text
         location
         location_sort
         last_modification
         highlight_color
        '''
        self.conn.execute('''
            INSERT OR REPLACE INTO {0}
             (book_id,
              annotation_id,
              epubcfi,
              highlight_text,
              note_text,
              location,
              location_sort,
              last_modification,
              highlight_color)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)'''.format(annotations_db),
              (annotation['book_id'],
              annotation['annotation_id'],
              annotation['epubcfi'],
              annotation['highlight_text'],
              annotation['note_text'],
              annotation['location'],
              annotation['location_sort'],
              annotation['last_modification'],
              annotation['highlight_color'])
             )

    def add_to_book_notes_db(self, book_notes_db, note):
        '''
        note is a dict containing the book_id and note_text to be stored
        '''
        self.conn.execute('''
            INSERT OR REPLACE INTO {0}
             (book_id,
              note_text)
            VALUES(?, ?)'''.format(book_notes_db),
             (note['book_id'],
              note['note_text'])
            )

    def add_to_bookmark_notes_db(self, bookmark_note_db, note):
        '''
        note is a dict containing:
        book_id, highlight_color, location, note_text, section_number
        '''
        self.conn.execute('''
            INSERT OR REPLACE INTO {0}
             (book_id,
              highlight_color,
              location,
              note_text,
              section_number)
            VALUES(?, ?, ?, ?, ?)'''.format(bookmark_note_db),
             (note['book_id'],
              note['highlight_color'],
              note['location'],
              note['note_text'],
              note['section_number'])
            )

    def add_to_books_db(self, books_db, book):
        '''
        book is a dict containing the metadata describing the book:
         book_id - unique per book for the reader app
        '''
        self.conn.execute('''INSERT OR REPLACE INTO {0}
                                   (
                                    active,
                                    author,
                                    author_sort,
                                    book_id,
                                    genre,
                                    path,
                                    title,
                                    title_sort,
                                    uuid
                                    )
                                   VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)'''.format(books_db),
                                   (
                                    book['active'],
                                    book['author'],
                                    book['author_sort'],
                                    book['book_id'],
                                    book['genre'],
                                    book['path'],
                                    book['title'],
                                    book['title_sort'],
                                    book['uuid']
                                    )
                                )

    def add_to_transient_db(self, transient_db, annotation):
        '''
        Store a captured annotation in preparation for re-rendering
            book_id
            genre
            hash
            highlight_color
            highlight_text
            last_modification
            location
            location_sort
            note_text
            reader
        '''
        self.conn.execute('''
            INSERT OR REPLACE INTO {0}
             (book_id,
              genre,
              hash,
              highlight_color,
              highlight_text,
              location,
              location_sort,
              last_modification,
              note_text,
              reader)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''.format(transient_db),
             (annotation['book_id'],
              annotation['genre'],
              annotation['hash'],
              annotation['highlight_color'],
              annotation['highlight_text'],
              annotation['location'],
              annotation['location_sort'],
              annotation['last_modification'],
              annotation['note_text'],
              annotation['reader']
              )
             )
        self.commit()

    def annotations_to_html(self, annotations_db, book_mi):
        """
        Return annotations in HTML format
        """

        def _row_to_dict(ann):
            # Convert sqlite row object to dict
            # Convert timestamp to float
            # Translation table: sqlite field:Annotation
            xl = {
                  'last_modification': 'timestamp',
                  'highlight_color': 'highlightcolor',
                  'location': 'location',
                  'location_sort': 'location_sort',
                  'note_text': 'note',
                  'highlight_text': 'text'
                  }
            ann_dict = {}
            for key in ann.keys():
                new_key = xl[key]
                if key == 'last_modification' and ann[key] is not None:
                    ann_dict[new_key] = float(ann[key])
                elif key in ['note_text', 'highlight_text']:
                    # Store text/notes as lists, split on line breaks
                    if ann[key]:
                        ann_dict[new_key] = ann[key].split('\n')
                    else:
                        ann_dict[new_key] = None
                else:
                    ann_dict[new_key] = ann[key]
            return ann_dict

        # Create an Annotations object to hold annotations
        stored_annotations = Annotations(self.opts, title=book_mi['title'])
        annotations = self.get_annotations(annotations_db, book_mi[b'book_id'])
        for ann in annotations:
            ann = _row_to_dict(ann)
            ann['reader_app'] = book_mi['reader_app']
            ann['genre'] = book_mi['genre']
            this_annotation = Annotation(ann)
            stored_annotations.annotations.append(this_annotation)
        soup = stored_annotations.to_HTML(stored_annotations.create_soup())
        return soup

    def annotations_to_text(self, annotations_db, book_mi):
        """
        Return annotations in text format
        """
        def _row_to_dict(ann):
            # Convert sqlite row object to dict
            # Convert timestamp to float
            # Translation table: sqlite field:Annotation
            xl = {
                  'last_modification': 'timestamp',
                  'highlight_color': 'highlightcolor',
                  'note_text': 'note',
                  'highlight_text': 'text'
                  }
            ann_dict = {}
            for key in ann.keys():
                new_key = xl[key]
                if key == 'last_modification' and ann[key] is not None:
                    ann_dict[new_key] = float(ann[key])
                elif key in ['note_text', 'highlight_text']:
                    # Store text/notes as lists, split on line breaks
                    if ann[key]:
                        ann_dict[new_key] = ann[key].split('\n')
                    else:
                        ann_dict[new_key] = None
                else:
                    ann_dict[new_key] = ann[key]
            return ann_dict

        # Create an Annotations object to hold annotations
        stored_annotations = Annotations(self.opts, title=book_mi['title'])
        annotations = self.get_annotations(annotations_db, book_mi[b'book_id'])
        for ann in annotations:
            ann = _row_to_dict(ann)
            ann['reader_app'] = book_mi['reader_app']
            this_annotation = Annotation(ann)
            stored_annotations.annotations.append(this_annotation)

        return stored_annotations.to_text()

    def capture_content(self, uas, book_id, transient_db):
        '''
        Store a set of annotations to the transient table
        '''
        self.create_annotations_transient_table(transient_db)
        for ua in uas:
            if isinstance(ua, NavigableString):
                continue
            if ua.name != 'div' or ua['class'] != "annotation":
                continue
            this_ua = AnnotationStruct()
            this_ua.book_id = book_id
            this_ua.hash = ua['hash']
            try:
                this_ua.genre = ua['genre']
            except:
                this_ua.genre = None

            this_ua.highlight_color = ua.find('table')['color']
            this_ua.reader = ua['reader']

            this_ua.last_modification = ua.find('td', 'timestamp')['uts']
            this_ua.location = ua.find('td', 'location').string
            this_ua.location_sort = ua['location_sort']

            try:
                pels = ua.findAll('p', 'highlight')
                this_ua.highlight_text = ''
                for pel in pels:
                    this_ua.highlight_text += pel.string + '\n'
            except:
                pass

            try:
                nels = ua.findAll('p', 'note')
                this_ua.note_text = ''
                for nel in nels:
                    this_ua.note_text += nel.string + '\n'
            except:
                pass

            self.add_to_transient_db(transient_db, this_ua)

    def close(self):
        if self.conn:
            self.conn.close()

    def connect(self):
        db_existed = os.path.exists(self.path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        if not db_existed:
            self.set_user_version(self.version)
        self.db_version = self.get_user_version()
        self._log_location("db_version: %s" % (self.db_version))
        self.create_timestamp_table()
        return self.conn

    def commit(self):
        self.conn.commit()

    def create_annotations_table(self, cached_db):
        """

        """

        self.conn.executescript('''
            DROP TABLE IF EXISTS "{0}";
            CREATE TABLE "{0}"
                (
                annotation_id TEXT UNIQUE,
                book_id TEXT,
                epubcfi TEXT,
                highlight_text TEXT,
                note_text TEXT,
                location TEXT,
                location_sort TEXT,
                last_modification TEXT,
                highlight_color TEXT
                );'''.format(cached_db))

    def create_annotations_transient_table(self, transient_table):
        '''
        Used to temporarily store annotations when moving or re-rendering
        '''
        self.conn.executescript('''
            DROP TABLE IF EXISTS "{0}";
            CREATE TABLE "{0}"
                (
                book_id TEXT,
                genre TEXT,
                hash TEXT,
                highlight_color TEXT,
                highlight_text TEXT,
                note_text TEXT,
                last_modification TEXT,
                location TEXT,
                location_sort TEXT,
                reader TEXT
                );'''.format(transient_table))

    def create_book_notes_table(self, cached_db):
        """
        """
        self.conn.executescript('''
            DROP TABLE IF EXISTS "{0}";
            CREATE TABLE "{0}"
                (
                book_id TEXT,
                note_text TEXT
                );'''.format(cached_db))

    def create_bookmark_notes_table(self, cached_db):
        """

        """

        self.conn.executescript('''
            DROP TABLE IF EXISTS "{0}";
            CREATE TABLE "{0}"
                (
                book_id TEXT,
                section_number TEXT,
                location TEXT,
                highlight_color TEXT,
                note_text TEXT
                );'''.format(cached_db))

    def create_books_table(self, cached_db):
        """

        """
        self.conn.executescript('''
            DROP TABLE IF EXISTS "{0}";
            CREATE TABLE "{0}"
                (
                 book_id TEXT UNIQUE,
                 title TEXT,
                 title_sort TEXT,
                 author TEXT,
                 author_sort TEXT,
                 genre TEXT,
                 uuid TEXT,
                 path TEXT,
                 active INTEGER NOT NULL,
                 last_annotation DATETIME
                );'''.format(cached_db))

    def create_timestamp_table(self):
        #c = self.conn.cursor()
        self.conn.execute('''CREATE TABLE IF NOT EXISTS timestamps
                     (db TEXT UNIQUE,
                      timestamp DATETIME)
                     ''')
        self.conn.commit()

    def get(self, *args, **kw):
        ans = self.conn.execute(*args)
        if not kw.get('all', True):
            ans = ans.fetchone()
            if not ans:
                ans = [None]
            return ans[0]
        return ans.fetchall()

    def get_annotation_count(self, annotations_db, book_id):
        """
        Count annotations from annotations_db for book_id
        """
        annotations = self.get("""SELECT
                                   highlight_text
                                  FROM {0}
                                  WHERE book_id = '{1}'""".format(annotations_db, book_id))
        return len(annotations)

    def get_annotations(self, annotations_db, book_id):
        """
        Get annotations from annotations_db for book_id
        """
        annotations = self.get("""SELECT
                                   highlight_text,
                                   note_text,
                                   highlight_color,
                                   last_modification,
                                   location,
                                   location_sort
                                  FROM {0}
                                  WHERE book_id = '{1}'""".format(annotations_db, book_id))

        return annotations

    def get_book_notes(self, book_notes_table, book_id):
        """
        Get Book notes from book_notes_db for book_id
        """
        book_notes = self.get("""SELECT
                                  note_text
                                 FROM {0}
                                 WHERE book_id = '{1}'""".format(book_notes_table, book_id))
        return book_notes

    def get_bookmark_notes(self, bookmark_notes_table, book_id):
        """
        Get Bookmark notes from bookmark_notes_db for book_id
        """
        bookmark_notes = self.get("""SELECT
                                      highlight_color,
                                      location,
                                      note_text,
                                      section_number
                                     FROM {0}
                                     WHERE book_id = '{1}'""".format(bookmark_notes_table, book_id))
        return bookmark_notes

    def get_books(self, books_db):
        """
        Get books from books_db
        """
        books = None
        table_exists = self.get('''SELECT name
                                   FROM sqlite_master
                                   WHERE type='table' AND name='{0}'
                                '''.format(books_db))
        if table_exists:
            books = self.get('''SELECT
                                 active,
                                 author,
                                 author_sort,
                                 book_id,
                                 genre,
                                 title,
                                 title_sort,
                                 uuid
                                FROM {0}'''.format(books_db))
        return books

    def get_genres(self, books_db, book_id):
        '''
        Return genres as list
        '''
        genre = self.get("""SELECT
                             genre
                            FROM {0}
                            WHERE book_id = '{1}'""".format(books_db, book_id))
        genres = []
        if genre:
            genres = genre[0][0].split(', ')
        return genres

    def get_last_update(self, books_db, book_id, as_timestamp=False):
        """
        Return the last annotation created for book_id
        """
        result = self.get("""SELECT
                              last_annotation
                             FROM {0}
                             WHERE book_id = '{1}'""".format(books_db, book_id))
        last_update = result[0]['last_annotation']
        if last_update:
            if not as_timestamp:
                last_update = self._timestamp_to_datestr(last_update)
        return last_update

    def get_title(self, books_db, book_id):
        title = self.get("""SELECT
                             title
                            FROM {0}
                            WHERE book_id = '{1}'""".format(books_db, book_id))
        return title[0][0]

    def get_transient_annotations(self, transient_db, book_id):
        '''
        Models get_annotations()
        '''
        annotations = self.get('''SELECT
                                   genre,
                                   hash,
                                   highlight_color,
                                   highlight_text,
                                   last_modification,
                                   location,
                                   location_sort,
                                   note_text,
                                   reader
                                  FROM {0}
                                  WHERE book_id = "{1}"'''.format(transient_db, book_id))

        return annotations

    def get_user_version(self):
        cur = self.conn.cursor()
        cur.execute('''PRAGMA user_version''')
        user_version = cur.fetchone()[0]
        return user_version

    def now(self):
        c = self.conn.cursor()
        c.execute("SELECT datetime('now', 'localtime')")
        return c.fetchone()[0]

    def purge_orphans(self, rac, preview):
        """
        rac: reader_app_class instance
        """
        self._log_location()

        cur = self.conn.cursor()

        # Find all active books in rac.books_db
        cur.execute('''SELECT * from {0}
                       WHERE active=1
                    '''.format(rac.books_db))
        rows = cur.fetchall()
        active_book_ids = []
        for row in rows:
            active_book_ids.append(row['book_id'])
        active_book_ids.sort()

        # Delete all annotations whose book_id is not active
        if preview:
            select = '''SELECT * from {0}
                        WHERE book_id NOT IN ({1})
                     '''.format(rac.annotations_db, ','.join(active_book_ids))
            cur.execute(select)
            rows = cur.fetchall()
            if rows:
                self._log(" !!! The following %d orphaned annotations would be removed: !!!" % len(rows))
            for row in rows:
                self._log("  book_id(%s):  %s" % (row['book_id'], row['highlight_text']))
        else:
            delete = '''DELETE from {0}
                        WHERE book_id NOT IN ({1})
                     '''.format(rac.annotations_db, ','.join(active_book_ids))
            self.conn.execute(delete)
            self.commit()

    def purge_widows(self, cached_db, preview):
        self._log_location(cached_db)
        cur = self.conn.cursor()
        if preview:
            cur.execute('''SELECT * from {0}
                           WHERE active=0 AND
                            last_annotation IS NULL
                        '''.format(cached_db))
            rows = cur.fetchall()
            if rows:
                self._log(" !!! the following inactive books without annotations would be removed: !!!")
            for row in rows:
                self._log("  '%s' by %s" % (row['title'], row['author']))

        else:
            self.conn.execute('''DELETE from {0}
                                 WHERE active=0 AND
                                  last_annotation IS NULL
                                   '''.format(cached_db))
            self.commit()

    def rerender_to_html(self, transient_table, book_id):
        '''
        Rerender a set of annotations with the current style
        Models annotations_to_html()
        '''
        def _row_to_dict(ann):
            # Convert sqlite row object to dict
            # Convert timestamp to float
            # Translation table: sqlite field:Annotation
            xl = {
                  'genre': 'genre',
                  'hash': 'hash',
                  'highlight_color': 'highlightcolor',
                  'highlight_text': 'text',
                  'last_modification': 'timestamp',
                  'location': 'location',
                  'location_sort': 'location_sort',
                  'note_text': 'note',
                  'reader': 'reader_app'
                  }
            ann_dict = {}
            for key in ann.keys():
                new_key = xl[key]
                if key == 'last_modification' and ann[key] is not None:
                    ann_dict[new_key] = float(ann[key])
                elif key in ['note_text', 'highlight_text']:
                    # Store text/notes as lists, split on line breaks
                    if ann[key]:
                        ann_dict[new_key] = ann[key].split('\n')
                    else:
                        ann_dict[new_key] = None
                else:
                    ann_dict[new_key] = ann[key]
            return ann_dict

        # Create an Annotations object to hold the re-rendered annotations
        rerendered_annotations = Annotations(self.opts)
        annotations = self.get_transient_annotations(transient_table, book_id)
        for ann in annotations:
            ann = _row_to_dict(ann)
            this_annotation = Annotation(ann)
            rerendered_annotations.annotations.append(this_annotation)
        soup = rerendered_annotations.to_HTML(stored_annotations.create_soup())
        return soup

    def set_user_version(self, db_version):
        self.conn.execute('''PRAGMA user_version={0}'''.format(db_version))

    def update_book_last_annotation(self, books_db, timestamp, book_id):
        self.conn.execute('''UPDATE {0}
                             SET last_annotation=?
                             WHERE book_id=?'''.format(books_db), (timestamp, book_id))

    def update_timestamp(self, cached_db):
        self.conn.execute(
            '''INSERT OR REPLACE INTO timestamps
               (db, timestamp) VALUES(?, ?)''',
               (cached_db, self.now()))

    # Helpers
    def _timestamp_to_datestr(self, timestamp):
        '''
        Convert timestamp to
        01 Jan 2011 12:34:56
        '''
        d = datetime.fromtimestamp(float(timestamp))
        return d.strftime('%d %b %Y %H:%M:%S')
