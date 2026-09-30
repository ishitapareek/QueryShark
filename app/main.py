from sqlalchemy import create_engine, Integer, String, Float, Column, ForeignKey, func
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

engine = create_engine("mysql+pymysql://root:admin@localhost:3306/QueryShark", echo = True)

Base = declarative_base()

class Person(Base):
    __tablename__ = 'people'
    id = Column(Integer, primary_key = True)
    name = Column(String(100), nullable = False)
    age = Column(Integer)

    things = relationship('Thing', back_populates = 'person')


class Thing(Base):
    __tablename__ = 'things'
    id = Column(Integer, primary_key = True)
    desc = Column(String(100), nullable = False)
    value = Column(Float)
    owner = Column(Integer, ForeignKey('people.id'))

    person = relationship('Person', back_populates = 'things')

Base.metadata.create_all(engine)

Session = sessionmaker(bind = engine)
session = Session()

# new_person = Person(name = 'M', age = 122)
# session.add(new_person)

# session.flush()

# new_thing = Thing(desc = 'Camera', value = 200.50, owner = new_person.id)
# session.add(new_thing)
# session.commit()

# print(new_person.things)
# print(new_thing.person.name)

result = session.query(Person.name, Thing.owner, func.count(Thing.id)).join(Person).group_by(Thing.owner).all()
session.commit()

print(result)

session.close()