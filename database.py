import peewee

from datetime import datetime
from peewee import SqliteDatabase, Model, TextField, DateTimeField

database = SqliteDatabase("database.db")


class BaseModel(Model):
    class Meta:
        database = database


class Manga(BaseModel):
    title = TextField(unique=True)
    url = TextField()
    domain_name = TextField()
    updated_date = DateTimeField(null=True)
    created_date = DateTimeField(default=datetime.now())

    class Meta:
        database = database


class Helper:

    def create_tables(self):
        with database:
            database.create_tables([Manga])

    def _insert(self, title: str, url: str, domain_name: str):
        try:
            if url != self.get_title(title).url:
                with database.atomic():
                    (
                        Manga.update(
                            url=url,
                            domain_name=domain_name,
                            updated_date=datetime.now(),
                        )
                        .where(Manga.title == title)
                        .execute()
                    )
            else:
                with database.atomic():
                    Manga.insert(
                        title=title, url=url, domain_name=domain_name
                    ).execute()
        except peewee.IntegrityError:
            pass
        except AttributeError:
            with database.atomic():
                Manga.insert(title=title, url=url, domain_name=domain_name).execute()

    def get(self, _id: int):
        return Manga.get(Manga.id == _id)

    def delete_one(self, _id: int):
        return Manga.get(Manga.id == _id).delete_instance()

    def get_title(self, title: str):
        try:
            return Manga.get(Manga.title == title)
        except Exception:
            pass

    def get_all(self):
        return Manga.select()

    def get_domain_names(self):
        return Manga.select(Manga.domain_name).distinct().order_by(+Manga.domain_name)

    def get_all_by_domain_name(self, domain_name: str):
        return (
            Manga.select().where(Manga.domain_name == domain_name).order_by(Manga.title)
        )
