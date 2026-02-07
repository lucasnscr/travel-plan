"""Fixture data matching real Booking.com RapidAPI response structures.

These responses are based on the Booking.com API via RapidAPI and are
used to test the BookingProvider without hitting the real API.
"""

SEARCH_DESTINATION_RESPONSE = {
    "status": True,
    "message": "Success",
    "data": [
        {
            "dest_id": "-1456928",
            "search_type": "city",
            "dest_type": "city",
            "city_name": "Paris",
            "country": "France",
            "label": "Paris, Île-de-France, France",
            "latitude": 48.8566,
            "longitude": 2.3522,
        },
        {
            "dest_id": "234567",
            "search_type": "region",
            "dest_type": "region",
            "city_name": "Paris Region",
            "country": "France",
            "label": "Paris Region, France",
            "latitude": 48.85,
            "longitude": 2.35,
        },
    ],
}

SEARCH_DESTINATION_EMPTY_RESPONSE: dict = {
    "status": True,
    "message": "Success",
    "data": [],
}

SEARCH_HOTELS_RESPONSE = {
    "status": True,
    "message": "Success",
    "data": {
        "hotels": [
            {
                "property": {
                    "id": 12345,
                    "name": "Grand Hotel Paris",
                    "propertyClass": 4,
                    "reviewScore": 8.7,
                    "reviewCount": 2341,
                    "latitude": 48.8566,
                    "longitude": 2.3522,
                    "wishlistName": "Le Marais",
                    "photoUrls": [
                        "https://example.com/photo1.jpg",
                        "https://example.com/photo2.jpg",
                    ],
                    "priceBreakdown": {
                        "grossPrice": {
                            "value": 450.0,
                            "currency": "EUR",
                        },
                    },
                    "externalUrl": "https://booking.com/hotel/fr/grand-paris",
                },
            },
            {
                "property": {
                    "id": 67890,
                    "name": "Budget Inn Bastille",
                    "propertyClass": 2,
                    "reviewScore": 7.2,
                    "reviewCount": 567,
                    "latitude": 48.8530,
                    "longitude": 2.3700,
                    "wishlistName": "Bastille",
                    "photoUrls": [
                        "https://example.com/photo3.jpg",
                    ],
                    "priceBreakdown": {
                        "grossPrice": {
                            "value": 150.0,
                            "currency": "EUR",
                        },
                    },
                    "deeplink": "https://booking.com/hotel/fr/budget-bastille",
                },
            },
            {
                "property": {
                    "id": 11111,
                    "name": "Luxury Suites Champs",
                    "propertyClass": 5,
                    "reviewScore": 9.4,
                    "reviewCount": 890,
                    "latitude": 48.8698,
                    "longitude": 2.3076,
                    "wishlistName": "Champs-Élysées",
                    "photoUrls": [],
                    "priceBreakdown": {
                        "grossPrice": {
                            "value": 890.0,
                            "currency": "EUR",
                        },
                    },
                    "externalUrl": "https://booking.com/hotel/fr/luxury-champs",
                },
            },
        ],
    },
}

HOTEL_DETAILS_RESPONSE = {
    "status": True,
    "message": "Success",
    "data": {
        "hotel_name": "Grand Hotel Paris",
        "class": 4,
        "description": "A beautiful 4-star hotel in the heart of Paris.",
        "address": "15 Rue de Rivoli, 75004 Paris",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "district": "Le Marais",
        "review_score": 8.7,
        "review_score_word": "Excellent",
        "review_nr": 2341,
        "checkin": {"from": "14:00", "until": "23:00"},
        "checkout": {"until": "11:00"},
        "photos": [
            {"url_original": "https://example.com/photo1_full.jpg", "url_max": "https://example.com/photo1_max.jpg"},
            {"url_original": "https://example.com/photo2_full.jpg", "url_max": "https://example.com/photo2_max.jpg"},
        ],
        "rooms": {
            "1": {
                "id": 101,
                "name": "Superior Double Room",
                "room_type": "double",
                "max_persons": 2,
                "bed_type": "King",
                "room_surface_in_m2": 28,
                "photos": [
                    {"url_original": "https://example.com/room1.jpg"},
                ],
            },
            "2": {
                "id": 102,
                "name": "Deluxe Suite",
                "room_type": "suite",
                "max_persons": 3,
                "bed_type": "King + Sofa",
                "room_surface_in_m2": 55,
                "photos": [],
            },
        },
        "facilities_block": {
            "facilities": [
                {"name": "Free WiFi", "facility_type_name": "connectivity"},
                {"name": "Swimming pool", "facility_type_name": "wellness"},
                {"name": "Restaurant", "facility_type_name": "food_drink"},
                {"name": "Fitness center", "facility_type_name": "wellness"},
                {"name": "Air conditioning", "facility_type_name": "room"},
            ],
        },
    },
}

SEARCH_BY_COORDINATES_RESPONSE = {
    "status": True,
    "message": "Success",
    "data": {
        "hotels": [
            {
                "property": {
                    "id": 22222,
                    "name": "Hotel Near Eiffel",
                    "propertyClass": 3,
                    "reviewScore": 8.1,
                    "reviewCount": 1200,
                    "latitude": 48.8584,
                    "longitude": 2.2945,
                    "wishlistName": "Champ de Mars",
                    "photoUrls": ["https://example.com/eiffel.jpg"],
                    "priceBreakdown": {
                        "grossPrice": {
                            "value": 220.0,
                            "currency": "EUR",
                        },
                    },
                    "externalUrl": "https://booking.com/hotel/fr/near-eiffel",
                },
            },
        ],
    },
}
