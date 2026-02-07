"""Fixture data matching real Google Places API (New) response structures.

These responses are based on the Google Places API (New) and Maps Platform
APIs and are used to test the GooglePlacesProvider without hitting the real API.
"""

TEXT_SEARCH_RESPONSE = {
    "places": [
        {
            "id": "ChIJLU7jZClu5kcR4PcOOO6p3I0",
            "displayName": {"text": "Musée du Louvre", "languageCode": "fr"},
            "formattedAddress": "Rue de Rivoli, 75001 Paris, France",
            "location": {"latitude": 48.8606, "longitude": 2.3376},
            "rating": 4.7,
            "userRatingCount": 342567,
            "priceLevel": "PRICE_LEVEL_MODERATE",
            "types": ["museum", "tourist_attraction", "point_of_interest"],
            "primaryType": "museum",
            "photos": [
                {
                    "name": "places/ChIJLU7jZClu5kcR4PcOOO6p3I0/photos/photo1",
                    "widthPx": 4032,
                    "heightPx": 3024,
                    "authorAttributions": [
                        {"displayName": {"text": "Photographer A"}},
                    ],
                },
                {
                    "name": "places/ChIJLU7jZClu5kcR4PcOOO6p3I0/photos/photo2",
                    "widthPx": 3000,
                    "heightPx": 2000,
                    "authorAttributions": [],
                },
            ],
            "currentOpeningHours": {
                "openNow": True,
                "weekdayDescriptions": [
                    "Monday: Closed",
                    "Tuesday: 9:00 AM – 6:00 PM",
                    "Wednesday: 9:00 AM – 6:00 PM",
                    "Thursday: 9:00 AM – 9:00 PM",
                    "Friday: 9:00 AM – 6:00 PM",
                    "Saturday: 9:00 AM – 6:00 PM",
                    "Sunday: 9:00 AM – 6:00 PM",
                ],
            },
            "websiteUri": "https://www.louvre.fr",
            "internationalPhoneNumber": "+33 1 40 20 53 17",
            "editorialSummary": {
                "text": "The world's largest art museum and a historic monument.",
            },
        },
        {
            "id": "ChIJATr1n-Fx5kcRjQb6q6cdQDY",
            "displayName": {"text": "Tour Eiffel", "languageCode": "fr"},
            "formattedAddress": "Champ de Mars, 5 Avenue Anatole France, 75007 Paris",
            "location": {"latitude": 48.8584, "longitude": 2.2945},
            "rating": 4.6,
            "userRatingCount": 245890,
            "types": ["tourist_attraction", "point_of_interest"],
            "primaryType": "tourist_attraction",
            "photos": [
                {
                    "name": "places/ChIJATr1n-Fx5kcRjQb6q6cdQDY/photos/eiffel1",
                    "widthPx": 4000,
                    "heightPx": 6000,
                    "authorAttributions": [
                        {"displayName": {"text": "Paris Photos"}},
                    ],
                },
            ],
            "websiteUri": "https://www.toureiffel.paris",
            "editorialSummary": {
                "text": "Iconic iron lattice tower on the Champ de Mars.",
            },
        },
    ],
}

TEXT_SEARCH_EMPTY_RESPONSE: dict = {
    "places": [],
}

NEARBY_SEARCH_RESPONSE = {
    "places": [
        {
            "id": "ChIJNearby1234",
            "displayName": {"text": "Café de Flore", "languageCode": "fr"},
            "formattedAddress": "172 Boulevard Saint-Germain, 75006 Paris",
            "location": {"latitude": 48.8541, "longitude": 2.3326},
            "rating": 4.2,
            "userRatingCount": 15670,
            "priceLevel": "PRICE_LEVEL_EXPENSIVE",
            "types": ["cafe", "restaurant", "food"],
            "primaryType": "cafe",
            "photos": [],
            "editorialSummary": {
                "text": "Historic literary café in Saint-Germain-des-Prés.",
            },
        },
    ],
}

PLACE_DETAILS_RESPONSE = {
    "id": "ChIJLU7jZClu5kcR4PcOOO6p3I0",
    "displayName": {"text": "Musée du Louvre", "languageCode": "fr"},
    "formattedAddress": "Rue de Rivoli, 75001 Paris, France",
    "location": {"latitude": 48.8606, "longitude": 2.3376},
    "rating": 4.7,
    "userRatingCount": 342567,
    "priceLevel": "PRICE_LEVEL_MODERATE",
    "types": ["museum", "tourist_attraction"],
    "primaryType": "museum",
    "photos": [
        {
            "name": "places/ChIJLU7jZClu5kcR4PcOOO6p3I0/photos/photo1",
            "widthPx": 4032,
            "heightPx": 3024,
            "authorAttributions": [
                {"displayName": {"text": "Photographer A"}},
            ],
        },
        {
            "name": "places/ChIJLU7jZClu5kcR4PcOOO6p3I0/photos/photo2",
            "widthPx": 3000,
            "heightPx": 2000,
            "authorAttributions": [],
        },
    ],
    "currentOpeningHours": {
        "openNow": True,
        "weekdayDescriptions": [
            "Monday: Closed",
            "Tuesday: 9:00 AM – 6:00 PM",
            "Wednesday: 9:00 AM – 6:00 PM",
            "Thursday: 9:00 AM – 9:00 PM",
            "Friday: 9:00 AM – 6:00 PM",
            "Saturday: 9:00 AM – 6:00 PM",
            "Sunday: 9:00 AM – 6:00 PM",
        ],
    },
    "regularOpeningHours": {
        "weekdayDescriptions": [
            "Monday: Closed",
            "Tuesday: 9:00 AM – 6:00 PM",
        ],
    },
    "websiteUri": "https://www.louvre.fr",
    "internationalPhoneNumber": "+33 1 40 20 53 17",
    "editorialSummary": {
        "text": "The world's largest art museum and a historic monument.",
    },
    "reviews": [
        {
            "authorAttribution": {"displayName": "Jean D."},
            "rating": 5,
            "originalText": {
                "text": "Incredible museum, could spend days here!",
                "languageCode": "en",
            },
            "publishTime": "2025-01-15T10:30:00Z",
        },
        {
            "authorAttribution": {"displayName": "Maria S."},
            "rating": 4,
            "originalText": {
                "text": "Beautiful but very crowded. Go early morning.",
                "languageCode": "en",
            },
            "publishTime": "2025-02-01T14:20:00Z",
        },
    ],
    "viewport": {
        "low": {"latitude": 48.859, "longitude": 2.335},
        "high": {"latitude": 48.862, "longitude": 2.340},
    },
    "googleMapsUri": "https://maps.google.com/?cid=10190932218279774176",
    "businessStatus": "OPERATIONAL",
}

DIRECTIONS_RESPONSE = {
    "geocoded_waypoints": [
        {"geocoder_status": "OK", "place_id": "ChIJOrigin123"},
        {"geocoder_status": "OK", "place_id": "ChIJDest456"},
    ],
    "routes": [
        {
            "summary": "Rue de Rivoli",
            "legs": [
                {
                    "distance": {"text": "2.1 km", "value": 2100},
                    "duration": {"text": "26 min", "value": 1560},
                    "start_address": "Louvre, Paris, France",
                    "end_address": "Tour Eiffel, Paris, France",
                    "steps": [
                        {
                            "html_instructions": "Head <b>west</b> on <b>Rue de Rivoli</b>",
                            "distance": {"text": "0.8 km", "value": 800},
                            "duration": {"text": "10 min", "value": 600},
                            "travel_mode": "WALKING",
                        },
                        {
                            "html_instructions": "Turn <b>left</b> onto <b>Pont Royal</b>",
                            "distance": {"text": "0.3 km", "value": 300},
                            "duration": {"text": "4 min", "value": 240},
                            "travel_mode": "WALKING",
                        },
                        {
                            "html_instructions": "Continue on <b>Quai d'Orsay</b>",
                            "distance": {"text": "1.0 km", "value": 1000},
                            "duration": {"text": "12 min", "value": 720},
                            "travel_mode": "WALKING",
                        },
                    ],
                },
            ],
            "overview_polyline": {
                "points": "q`eiHurjMAB@DCBA",
            },
        },
    ],
    "status": "OK",
}

DIRECTIONS_NO_ROUTE_RESPONSE: dict = {
    "routes": [],
    "status": "ZERO_RESULTS",
}

GEOCODE_RESPONSE = {
    "results": [
        {
            "place_id": "ChIJD7fiBh9u5kcRYJSMaMOCCwQ",
            "formatted_address": "Paris, France",
            "geometry": {
                "location": {"lat": 48.8566, "lng": 2.3522},
            },
            "types": ["locality", "political"],
        },
    ],
    "status": "OK",
}

GEOCODE_EMPTY_RESPONSE: dict = {
    "results": [],
    "status": "ZERO_RESULTS",
}

REVERSE_GEOCODE_RESPONSE = {
    "results": [
        {
            "place_id": "ChIJRevGeo123",
            "formatted_address": "1 Rue de Rivoli, 75001 Paris, France",
            "geometry": {
                "location": {"lat": 48.8606, "lng": 2.3376},
            },
            "types": ["street_address"],
        },
        {
            "place_id": "ChIJRevGeo456",
            "formatted_address": "1er Arrondissement, Paris, France",
            "geometry": {
                "location": {"lat": 48.8600, "lng": 2.3400},
            },
            "types": ["sublocality", "political"],
        },
    ],
    "status": "OK",
}
