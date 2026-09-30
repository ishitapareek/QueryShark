from sqlalchemy import ForeignKey
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Float, func

engine = create_engine("mysql+pymysql://root:admin@localhost:3306/QueryShark", echo = True)

# conn = engine.connect()

# conn.execute(text("SELECT * FROM QueryRuns"))

# conn.commit()

# from sqlalchemy.orm import Session

# session = Session(engine)
# session.execute(text('INSERT INTO QueryRuns (current_schema, sql_text, duration_ms, status) VALUES ("x", "test", 0.3, "FAST")'))

# session.commit()

meta = MetaData()

table = Table(
    'test',
    meta,
    Column('id', Integer, primary_key = True),
    Column('name', String(50), nullable = False),
    Column('age', Integer)
)

meta.create_all(engine)

conn = engine.connect() 

# insert_statement = insert(table).values(name = "abc", age = 30)
# result = conn.execute(insert_statement)

# conn.commit()

# select_statement = table.select().where(table.c.id == 1)
# result = conn.execute(select_statement)

# for row in result.fetchall():
#     print(row)

update_statement = table.update().where(table.c.id == 1).values(age = 10)
conn.execute(update_statement) 
conn.commit()

delete_statement = table.delete().where(table.c.id == 1)
conn.execute(delete_statement)
conn.commit()

things = Table(
    'things',
    meta,
    Column('id', Integer, primary_key = True),
    Column('desc', String(100), nullable = False),
    Column('value', Float),
    Column('owner', Integer, ForeignKey('test.id'))
)

meta.create_all(engine) 

insert_test = table.insert().values([
    {'name' : 'Mike', 'age' : 5},
    {'name' : 'John', 'age' : 54},
    {'name' : 'Bob', 'age' : 51},
])

insert_things = things.insert().values([
    {'owner' : 2, 'desc' : 'Laptop', 'value' : 200.32}, 
    {'owner' : 2, 'desc' : 'Phone', 'value' : 55.50}, 
    {'owner' : 3, 'desc' : 'TV', 'value' : 123.42}, 
    {'owner' : 4, 'desc' : 'Mouse', 'value' : 2044.422}, 
    {'owner' : 5, 'desc' : 'Book', 'value' : 12.30}, 
])

conn.execute(insert_test)
conn.execute(insert_things)

conn.commit()

join_statement = table.join(things, table.c.id == things.c.owner)
select_statement = table.select().with_only_columns(table.c.name, things.c.desc).select_from(join_statement)

result = conn.execute(select_statement)
conn.commit()

for row in result.fetchall():
    print(row)


groupbystatement = things.select().with_only_columns(things.c.owner, func.sum(things.c.value)).group_by(things.c.owner).having(func.sum(things.c.value) > 1000) 
result = conn.execute(groupbystatement)

for row in result.fetchall():
    print(row)