from sqlalchemy import select
from app.models.memory import Memory, Person

def get_or_create_person(db, user_id: str, name: str) -> Person:
    name = name.strip()
    stmt = select(Person).where(Person.user_id == user_id, Person.name.ilike(name))
    existing = db.scalars(stmt).first()
    if existing:
        return existing
    person = Person(user_id=user_id, name=name)
    db.add(person)
    db.commit()
    db.refresh(person)
    return person

def link_person_to_memory(db, person: Person, memory: Memory) -> None:
    if person not in memory.people:
        memory.people.append(person)
        db.commit()

def get_people_for_user(db, user_id: str) -> list[Person]:
    stmt = select(Person).where(Person.user_id == user_id).order_by(Person.name)
    return list(db.scalars(stmt))

def get_memories_for_person(db, user_id: str, person_id: str) -> list[Memory]:
    stmt = select(Person).where(Person.user_id == user_id, Person.id == person_id)
    person = db.scalars(stmt).first()
    return person.memories if person else []