def test_conversation_hello():
    response = simulate_conversation("Bonjour, comment ça va?")
    assert response == "Bonjour! Je vais bien, merci!"