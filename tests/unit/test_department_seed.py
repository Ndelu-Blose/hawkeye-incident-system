from app.extensions import db
from app.models import Authority, DepartmentContact
from scripts.import_departments_csv import import_departments_csv
from scripts.seed_departments import seed_departments


def test_seed_departments_creates_authority_and_contacts(app):
    with app.app_context():
        created_departments, created_contacts = seed_departments()
        assert created_departments >= 1
        assert created_contacts >= 1

        water = db.session.query(Authority).filter(Authority.code == "WATER_SANITATION").first()
        assert water is not None
        assert water.routing_enabled is True
        assert water.notifications_enabled is True

        email_contact = (
            db.session.query(DepartmentContact)
            .filter(
                DepartmentContact.authority_id == water.id,
                DepartmentContact.channel == "email",
            )
            .first()
        )
        assert email_contact is not None


def test_seed_departments_is_idempotent(app):
    with app.app_context():
        seed_departments()
        first_authority_count = db.session.query(Authority).count()
        first_contact_count = db.session.query(DepartmentContact).count()

        seed_departments()
        second_authority_count = db.session.query(Authority).count()
        second_contact_count = db.session.query(DepartmentContact).count()

        assert second_authority_count == first_authority_count
        assert second_contact_count == first_contact_count


def test_import_departments_csv_is_idempotent(app):
    with app.app_context():
        import_departments_csv()
        first_authority_count = db.session.query(Authority).count()
        first_contact_count = db.session.query(DepartmentContact).count()

        import_departments_csv()
        second_authority_count = db.session.query(Authority).count()
        second_contact_count = db.session.query(DepartmentContact).count()

        assert second_authority_count == first_authority_count
        assert second_contact_count == first_contact_count


def test_seed_departments_populates_contact_verification_metadata(app):
    with app.app_context():
        seed_departments()
        metro = db.session.query(Authority).filter(Authority.code == "METRO_POLICE").first()
        assert metro is not None
        contact = (
            db.session.query(DepartmentContact)
            .filter(
                DepartmentContact.authority_id == metro.id,
                DepartmentContact.channel == "email",
            )
            .first()
        )
        assert contact is not None
        assert contact.verification_status == "unverified"
        assert contact.is_primary is True
