"""F1 tests: customer cancellation and preparation-time estimate."""

import uuid

from app.db import cursor


def test_wait_time_is_hidden_before_preparation(anon, make_order, make_plat):
    dish = make_plat(temps_preparation=8)
    order = make_order(statut="recue", lignes=[(dish, 2)])

    response = anon.get(f"/api/suivi/{order['suivi_token']}/temps-attente")

    assert response.status_code == 200
    assert response.json() == {"visible": False, "temps_attente_minutes": None}


def test_wait_time_prepares_four_identical_food_items_in_parallel(anon, make_order, make_plat):
    burger = make_plat(temps_preparation=15)
    order = make_order(
        statut="en_preparation",
        lignes=[(burger, 4)],
    )

    response = anon.get(f"/api/suivi/{order['suivi_token']}/temps-attente")

    assert response.status_code == 200
    # Four burgers fit in the five-food-item parallel capacity.
    assert response.json() == {"visible": True, "temps_attente_minutes": 15}


def test_wait_time_uses_five_parallel_food_slots(anon, make_order, make_plat):
    dish = make_plat(temps_preparation=12)
    order = make_order(
        statut="en_preparation",
        lignes=[(dish, 6)],
    )

    response = anon.get(f"/api/suivi/{order['suivi_token']}/temps-attente")

    assert response.status_code == 200
    # Five units start together; the sixth starts when a slot becomes free.
    assert response.json() == {"visible": True, "temps_attente_minutes": 24}


def test_wait_time_uses_four_parallel_drink_slots(anon, make_order, make_plat):
    with cursor() as cur:
        cur.execute("SELECT id FROM categories WHERE lower(nom) = 'boissons' LIMIT 1")
        category = cur.fetchone()
    assert category is not None, "The test database must seed the Boissons category"

    drink = make_plat(temps_preparation=3, categorie_id=category["id"])
    order = make_order(
        statut="en_preparation",
        lignes=[(drink, 5)],
    )

    response = anon.get(f"/api/suivi/{order['suivi_token']}/temps-attente")

    assert response.status_code == 200
    # Four drinks start together; the fifth needs a second three-minute slot.
    assert response.json() == {"visible": True, "temps_attente_minutes": 6}


def test_food_and_drinks_are_prepared_at_the_same_time(anon, make_order, make_plat):
    with cursor() as cur:
        cur.execute("SELECT id FROM categories WHERE lower(nom) = 'boissons' LIMIT 1")
        category = cur.fetchone()
    assert category is not None, "The test database must seed the Boissons category"

    food = make_plat(temps_preparation=15)
    drink = make_plat(temps_preparation=3, categorie_id=category["id"])
    order = make_order(
        statut="en_preparation",
        lignes=[(food, 5), (drink, 4)],
    )

    response = anon.get(f"/api/suivi/{order['suivi_token']}/temps-attente")

    assert response.status_code == 200
    # 15 minutes for food and 3 for drinks happen concurrently, not 18 minutes.
    assert response.json() == {"visible": True, "temps_attente_minutes": 15}


def test_wait_time_rejects_unknown_or_invalid_token(anon):
    assert anon.get("/api/suivi/not-a-uuid/temps-attente").status_code == 404
    assert anon.get(f"/api/suivi/{uuid.uuid4()}/temps-attente").status_code == 404


def test_customer_can_cancel_received_order_and_online_payment_is_refunded(
    anon, make_order, get_order, get_history
):
    order = make_order(paiement_mode="en_ligne")

    response = anon.post(f"/api/suivi/{order['suivi_token']}/annuler")

    assert response.status_code == 200
    assert response.json()["statut"] == "annulee"
    assert response.json()["paiement_statut"] == "rembourse"
    assert get_order(order["id"])["statut"] == "annulee"
    assert get_order(order["id"])["paiement_statut"] == "rembourse"
    assert get_history(order["id"])[-1]["employe_id"] is None


def test_customer_can_cancel_cash_order_without_changing_payment_state(anon, make_order):
    order = make_order(paiement_mode="especes")

    response = anon.post(f"/api/suivi/{order['suivi_token']}/annuler")

    assert response.status_code == 200
    assert response.json()["statut"] == "annulee"
    assert response.json()["paiement_statut"] == "en_attente"


def test_customer_cannot_cancel_after_preparation_has_started(anon, make_order, get_order):
    order = make_order(statut="en_preparation")

    response = anon.post(f"/api/suivi/{order['suivi_token']}/annuler")

    assert response.status_code == 409
    assert get_order(order["id"])["statut"] == "en_preparation"


def test_cancel_rejects_unknown_or_invalid_token(anon):
    assert anon.post("/api/suivi/not-a-uuid/annuler").status_code == 404
    assert anon.post(f"/api/suivi/{uuid.uuid4()}/annuler").status_code == 404


def test_tracking_page_and_its_assets_are_served(anon):
    page = anon.get("/suivi.html")

    assert page.status_code == 200
    assert '/assets/js/public/tracking.js' in page.text
    assert '/assets/css/tracking.css' in page.text
    assert anon.get('/assets/js/public/tracking.js').status_code == 200
    assert anon.get('/assets/css/tracking.css').status_code == 200


def test_checkout_confirmation_shows_wait_time_after_order_summary(anon):
    response = anon.get("/assets/js/public/checkout.js")

    assert response.status_code == 200
    source = response.text
    assert 'id="confirmation-wait-time"' in source
    assert source.index('Votre numéro de commande') < source.index('Total :')
    assert source.index('Total :') < source.index('id="confirmation-wait-time"')
    assert "Disponible dès que votre commande passe en préparation." in source
    assert "/api/commandes/suivi/" in source
    assert "/api/suivi/" in source