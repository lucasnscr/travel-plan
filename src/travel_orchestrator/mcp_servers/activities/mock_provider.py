"""Deterministic mock provider for activity discovery.

Contains a curated database of activities for popular destinations,
with realistic hours, prices, categories, and seasonal events.
Same inputs always produce the same outputs (seeded RNG).
"""

from __future__ import annotations

import datetime
import hashlib
import random
from typing import Any

from travel_orchestrator.state.models import Activity

# ---------------------------------------------------------------------------
# Opening-hours templates
# ---------------------------------------------------------------------------

_MUSEUM_HOURS: dict[str, str] = {
    "monday": "closed",
    "tuesday": "10:00-18:00",
    "wednesday": "10:00-18:00",
    "thursday": "10:00-21:00",
    "friday": "10:00-18:00",
    "saturday": "10:00-18:00",
    "sunday": "10:00-18:00",
}
_RESTAURANT_HOURS: dict[str, str] = {
    "monday": "12:00-23:00",
    "tuesday": "12:00-23:00",
    "wednesday": "12:00-23:00",
    "thursday": "12:00-23:00",
    "friday": "12:00-00:00",
    "saturday": "12:00-00:00",
    "sunday": "12:00-22:00",
}
_TOUR_HOURS: dict[str, str] = {
    "monday": "09:00-17:00",
    "tuesday": "09:00-17:00",
    "wednesday": "09:00-17:00",
    "thursday": "09:00-17:00",
    "friday": "09:00-17:00",
    "saturday": "09:00-17:00",
    "sunday": "09:00-17:00",
}
_NATURE_HOURS: dict[str, str] = {
    "monday": "06:00-18:00",
    "tuesday": "06:00-18:00",
    "wednesday": "06:00-18:00",
    "thursday": "06:00-18:00",
    "friday": "06:00-18:00",
    "saturday": "06:00-18:00",
    "sunday": "06:00-18:00",
}
_SHOPPING_HOURS: dict[str, str] = {
    "monday": "10:00-21:00",
    "tuesday": "10:00-21:00",
    "wednesday": "10:00-21:00",
    "thursday": "10:00-21:00",
    "friday": "10:00-22:00",
    "saturday": "10:00-22:00",
    "sunday": "11:00-20:00",
}
_NIGHTLIFE_HOURS: dict[str, str] = {
    "monday": "closed",
    "tuesday": "closed",
    "wednesday": "21:00-03:00",
    "thursday": "21:00-03:00",
    "friday": "22:00-05:00",
    "saturday": "22:00-05:00",
    "sunday": "closed",
}

_HOURS_BY_CATEGORY: dict[str, dict[str, str]] = {
    "museum": _MUSEUM_HOURS,
    "restaurant": _RESTAURANT_HOURS,
    "tour": _TOUR_HOURS,
    "nature": _NATURE_HOURS,
    "shopping": _SHOPPING_HOURS,
    "nightlife": _NIGHTLIFE_HOURS,
}

# ---------------------------------------------------------------------------
# Interest → category mapping
# ---------------------------------------------------------------------------

INTEREST_TO_CATEGORIES: dict[str, list[str]] = {
    "history": ["museum", "tour"],
    "culture": ["museum", "tour"],
    "art": ["museum"],
    "food": ["restaurant"],
    "gastronomy": ["restaurant"],
    "nature": ["nature", "tour"],
    "adventure": ["nature", "tour"],
    "shopping": ["shopping"],
    "nightlife": ["nightlife"],
    "beach": ["nature"],
    "religion": ["museum", "tour"],
    "architecture": ["tour", "museum"],
    "music": ["nightlife", "tour"],
    "sports": ["nature", "tour"],
    "photography": ["tour", "nature"],
    "wine": ["restaurant", "tour"],
    "wellness": ["nature"],
}

# ---------------------------------------------------------------------------
# Activity database by destination (key = lowercase city name)
# ---------------------------------------------------------------------------

RawEntry = dict[str, Any]


def _a(
    *,
    name: str,
    category: str,
    tags: list[str],
    lat: float,
    lng: float,
    address: str,
    duration: int,
    price: float,
    currency: str = "BRL",
    requires_booking: bool = False,
    indoor: bool = True,
    description: str,
    base_score: float = 0.8,
) -> RawEntry:
    """Shorthand to build a raw activity entry."""
    return {
        "name": name,
        "category": category,
        "tags": tags,
        "lat": lat,
        "lng": lng,
        "address": address,
        "duration": duration,
        "price": price,
        "currency": currency,
        "requires_booking": requires_booking,
        "indoor": indoor,
        "description": description,
        "base_score": base_score,
    }


_ACTIVITIES_DB: dict[str, list[RawEntry]] = {
    "rio de janeiro": [
        _a(name="Cristo Redentor", category="tour", tags=["history", "religion", "photography"], lat=-22.9519, lng=-43.2105, address="Parque Nacional da Tijuca", duration=120, price=80, description="Visite uma das Sete Maravilhas do Mundo Moderno com vista panorâmica da cidade", indoor=False, requires_booking=True, base_score=0.98),
        _a(name="Pão de Açúcar", category="tour", tags=["nature", "photography", "adventure"], lat=-22.9492, lng=-43.1545, address="Av. Pasteur 520, Urca", duration=150, price=120, description="Passeio de bondinho com vistas deslumbrantes da Baía de Guanabara", indoor=False, requires_booking=True, base_score=0.96),
        _a(name="Praia de Copacabana", category="nature", tags=["beach", "nature", "sports"], lat=-22.9711, lng=-43.1822, address="Av. Atlântica, Copacabana", duration=180, price=0, description="A praia mais famosa do mundo — sol, mar e calçadão icônico", indoor=False, base_score=0.92),
        _a(name="Praia de Ipanema", category="nature", tags=["beach", "nature", "photography"], lat=-22.9838, lng=-43.2045, address="Av. Vieira Souto, Ipanema", duration=180, price=0, description="Praia sofisticada com pôr do sol espetacular no Arpoador", indoor=False, base_score=0.93),
        _a(name="Museu do Amanhã", category="museum", tags=["culture", "art", "history"], lat=-22.8942, lng=-43.1795, address="Praça Mauá 1, Centro", duration=120, price=30, description="Museu de ciências interativo projetado por Santiago Calatrava", indoor=True, base_score=0.88),
        _a(name="Maracanã Stadium Tour", category="tour", tags=["sports", "history", "culture"], lat=-22.9121, lng=-43.2302, address="R. Prof. Eurico Rabelo, Maracanã", duration=90, price=65, description="Tour pelo templo do futebol brasileiro, palco de duas finais de Copa", indoor=False, requires_booking=True, base_score=0.87),
        _a(name="Santa Teresa Walking Tour", category="tour", tags=["history", "art", "architecture"], lat=-22.9207, lng=-43.1821, address="Largo do Guimarães, Santa Teresa", duration=150, price=45, description="Passeio pelo bairro boêmio com ateliês, casarões coloniais e grafites", indoor=False, base_score=0.85),
        _a(name="Feira de São Cristóvão", category="restaurant", tags=["food", "culture", "music"], lat=-22.8967, lng=-43.2220, address="Campo de São Cristóvão, São Cristóvão", duration=180, price=0, description="Centro Luiz Gonzaga: comida nordestina, forró ao vivo e artesanato", indoor=False, base_score=0.86),
        _a(name="Jardim Botânico", category="nature", tags=["nature", "photography", "wellness"], lat=-22.9672, lng=-43.2248, address="R. Jardim Botânico 1008", duration=120, price=15, description="Jardim com 6.500 espécies de plantas tropicais, incluindo palmeiras imperiais", indoor=False, base_score=0.88),
        _a(name="Confeitaria Colombo", category="restaurant", tags=["food", "history", "culture"], lat=-22.9044, lng=-43.1768, address="R. Gonçalves Dias 32, Centro", duration=90, price=70, description="Confeitaria Belle Époque de 1894 com espelhos belgas e chá da tarde impecável", indoor=True, base_score=0.90),
        _a(name="Lapa Nightlife", category="nightlife", tags=["nightlife", "music", "culture"], lat=-22.9138, lng=-43.1805, address="Arcos da Lapa, Centro", duration=240, price=50, description="Samba, choro e MPB ao vivo nas casas noturnas sob os arcos coloniais", indoor=False, base_score=0.84),
        _a(name="Trilha da Pedra Bonita", category="nature", tags=["adventure", "nature", "sports"], lat=-22.9880, lng=-43.2845, address="Parque Nacional da Tijuca", duration=180, price=0, description="Trilha moderada com vista de 360° — ponto de partida de voo livre", indoor=False, base_score=0.82),
        _a(name="Shopping Leblon", category="shopping", tags=["shopping"], lat=-22.9832, lng=-43.2180, address="Av. Afrânio de Melo Franco 290", duration=120, price=0, description="Shopping premium com lojas de grife e gastronomia sofisticada", indoor=True, base_score=0.70),
    ],
    "são paulo": [
        _a(name="MASP", category="museum", tags=["art", "culture", "history"], lat=-23.5614, lng=-46.6558, address="Av. Paulista 1578", duration=120, price=50, description="Museu de Arte de São Paulo — acervo com Rembrandt, Van Gogh e arte brasileira", indoor=True, base_score=0.95),
        _a(name="Pinacoteca do Estado", category="museum", tags=["art", "culture", "history"], lat=-23.5342, lng=-46.6340, address="Praça da Luz 2, Luz", duration=120, price=20, description="Museu mais antigo de São Paulo com foco em arte brasileira do séc. XIX", indoor=True, base_score=0.90),
        _a(name="Mercadão — Mercado Municipal", category="restaurant", tags=["food", "gastronomy", "culture"], lat=-23.5418, lng=-46.6292, address="R. da Cantareira 306, Centro", duration=90, price=60, description="Vitrais art déco e o lendário sanduíche de mortadela", indoor=True, base_score=0.92),
        _a(name="Beco do Batman", category="tour", tags=["art", "photography", "culture"], lat=-23.5562, lng=-46.6878, address="R. Gonçalo Afonso, Vila Madalena", duration=60, price=0, description="Beco a céu aberto coberto de grafites — galeria urbana renovada constantemente", indoor=False, base_score=0.85),
        _a(name="Parque Ibirapuera", category="nature", tags=["nature", "sports", "photography"], lat=-23.5874, lng=-46.6576, address="Av. Pedro Álvares Cabral", duration=150, price=0, description="Maior parque urbano de SP — lagos, museus, ciclovia e muito verde", indoor=False, base_score=0.93),
        _a(name="Liberdade Walking Tour", category="tour", tags=["culture", "food", "history"], lat=-23.5576, lng=-46.6337, address="Praça da Liberdade, Liberdade", duration=120, price=0, description="Bairro japonês com feiras de rua, templos e a melhor culinária asiática da cidade", indoor=False, base_score=0.86),
        _a(name="Bar do Luiz Fernandes", category="restaurant", tags=["food", "nightlife"], lat=-23.5532, lng=-46.6913, address="R. Fradique Coutinho 1326, Vila Madalena", duration=120, price=80, description="Boteco autêntico com petiscos de boteco e chopp gelado", indoor=False, base_score=0.82),
        _a(name="Rua Oscar Freire", category="shopping", tags=["shopping"], lat=-23.5628, lng=-46.6710, address="R. Oscar Freire, Jardins", duration=120, price=0, description="Rua de compras mais sofisticada de SP — grifes nacionais e internacionais", indoor=False, base_score=0.75),
        _a(name="Theatro Municipal", category="museum", tags=["culture", "art", "architecture", "music"], lat=-23.5452, lng=-46.6386, address="Praça Ramos de Azevedo, Centro", duration=90, price=25, currency="BRL", description="Ópera inaugurada em 1911 com arquitetura eclética e programação de classe mundial", indoor=True, requires_booking=True, base_score=0.91),
        _a(name="Vila Madalena Night", category="nightlife", tags=["nightlife", "music"], lat=-23.5535, lng=-46.6920, address="Vila Madalena", duration=240, price=40, description="Bares e baladas no bairro mais alternativo de São Paulo", indoor=False, base_score=0.80),
    ],
    "paris": [
        _a(name="Musée du Louvre", category="museum", tags=["art", "history", "culture"], lat=48.8606, lng=2.3376, address="Rue de Rivoli, 1er", duration=240, price=22, currency="EUR", description="O maior museu de arte do mundo — da Mona Lisa à Vênus de Milo", indoor=True, requires_booking=True, base_score=0.99),
        _a(name="Tour Eiffel", category="tour", tags=["history", "photography", "architecture"], lat=48.8584, lng=2.2945, address="Champ de Mars, 7e", duration=120, price=29, currency="EUR", description="Ícone de Paris: subida ao topo com vista de toda a cidade", indoor=False, requires_booking=True, base_score=0.97),
        _a(name="Musée d'Orsay", category="museum", tags=["art", "culture", "architecture"], lat=48.8600, lng=2.3266, address="1 Rue de la Légion d'Honneur, 7e", duration=180, price=16, currency="EUR", description="Impressionismo em uma antiga estação ferroviária — Monet, Renoir, Degas", indoor=True, base_score=0.95),
        _a(name="Montmartre Walking Tour", category="tour", tags=["history", "art", "photography"], lat=48.8867, lng=2.3431, address="Place du Tertre, 18e", duration=150, price=0, currency="EUR", description="Ruelas de artistas, Sacré-Cœur e a vista mais romântica de Paris", indoor=False, base_score=0.90),
        _a(name="Le Marais Food Tour", category="restaurant", tags=["food", "gastronomy", "culture"], lat=48.8566, lng=2.3622, address="Rue des Rosiers, 4e", duration=180, price=85, currency="EUR", description="Falafel, pâtisseries e queijos artesanais no bairro mais charmoso", indoor=False, requires_booking=True, base_score=0.92),
        _a(name="Jardin du Luxembourg", category="nature", tags=["nature", "photography", "wellness"], lat=48.8462, lng=2.3372, address="Rue de Médicis, 6e", duration=90, price=0, currency="EUR", description="Jardim renascentista com fontes, esculturas e cadeiras verdes à sombra dos plátanos", indoor=False, base_score=0.88),
        _a(name="Galeries Lafayette", category="shopping", tags=["shopping", "architecture"], lat=48.8735, lng=2.3322, address="40 Bd Haussmann, 9e", duration=120, price=0, currency="EUR", description="Cúpula art nouveau e lojas de luxo no coração dos Grands Boulevards", indoor=True, base_score=0.82),
        _a(name="Moulin Rouge Show", category="nightlife", tags=["nightlife", "culture", "music"], lat=48.8842, lng=2.3323, address="82 Bd de Clichy, 18e", duration=150, price=120, currency="EUR", description="O cabaré mais famoso do mundo desde 1889 — show de can-can e champagne", indoor=True, requires_booking=True, base_score=0.88),
        _a(name="Croisière sur la Seine", category="tour", tags=["photography", "nature"], lat=48.8600, lng=2.2930, address="Port de la Bourdonnais, 7e", duration=75, price=18, currency="EUR", description="Cruzeiro ao entardecer pelos pontos icônicos de Paris vistos da água", indoor=False, base_score=0.89),
        _a(name="Catacombes de Paris", category="museum", tags=["history", "adventure"], lat=48.8339, lng=2.3324, address="1 Av. du Colonel Rol-Tanguy, 14e", duration=90, price=15, currency="EUR", description="Túneis subterrâneos com os ossos de 6 milhões de parisienses", indoor=True, requires_booking=True, base_score=0.86),
    ],
    "lisbon": [
        _a(name="Torre de Belém", category="museum", tags=["history", "architecture", "photography"], lat=38.6916, lng=-9.2160, address="Av. Brasília, Belém", duration=60, price=10, currency="EUR", description="Fortaleza manuelina à beira do Tejo — símbolo dos Descobrimentos", indoor=False, base_score=0.94),
        _a(name="Pastéis de Belém", category="restaurant", tags=["food", "gastronomy", "culture"], lat=38.6975, lng=-9.2034, address="R. de Belém 84-92", duration=45, price=8, currency="EUR", description="O pastel de nata original desde 1837 — receita secreta do mosteiro", indoor=True, base_score=0.95),
        _a(name="Alfama Walking Tour", category="tour", tags=["history", "culture", "photography"], lat=38.7114, lng=-9.1300, address="Miradouro de Santa Luzia, Alfama", duration=150, price=0, currency="EUR", description="Labirinto medieval com fado, azulejos e miradouros sobre o Tejo", indoor=False, base_score=0.92),
        _a(name="Oceanário de Lisboa", category="museum", tags=["nature", "culture"], lat=38.7634, lng=-9.0938, address="Esplanada Dom Carlos I, Parque das Nações", duration=120, price=25, currency="EUR", description="Um dos maiores oceanários da Europa — tubarões, lontras e recifes", indoor=True, requires_booking=True, base_score=0.90),
        _a(name="Time Out Market", category="restaurant", tags=["food", "gastronomy"], lat=38.7070, lng=-9.1457, address="Av. 24 de Julho 49, Cais do Sodré", duration=90, price=30, currency="EUR", description="Os melhores chefs de Lisboa sob o mesmo teto no Mercado da Ribeira", indoor=True, base_score=0.91),
        _a(name="Sintra Day Trip", category="tour", tags=["history", "nature", "architecture", "photography"], lat=38.7876, lng=-9.3908, address="Sintra", duration=360, price=15, currency="EUR", description="Palácios coloridos em floresta encantada — Pena, Mouros e Regaleira", indoor=False, requires_booking=False, base_score=0.96),
        _a(name="Bairro Alto Night", category="nightlife", tags=["nightlife", "music"], lat=38.7145, lng=-9.1449, address="Bairro Alto", duration=240, price=20, currency="EUR", description="Ruas estreitas repletas de bares, fado vadio e noite lisboeta", indoor=False, base_score=0.83),
        _a(name="LX Factory", category="shopping", tags=["shopping", "art", "culture"], lat=38.7036, lng=-9.1785, address="R. Rodrigues de Faria 103", duration=120, price=0, currency="EUR", description="Espaço industrial convertido com lojas indie, livraria e brunch", indoor=False, base_score=0.85),
        _a(name="Praia de Cascais", category="nature", tags=["beach", "nature"], lat=38.6960, lng=-9.4215, address="Cascais", duration=240, price=0, currency="EUR", description="Praia de areia dourada a 30 min de trem — mergulho, surfe e marisco", indoor=False, base_score=0.84),
    ],
    "tokyo": [
        _a(name="Senso-ji Temple", category="museum", tags=["history", "religion", "culture", "photography"], lat=35.7148, lng=139.7967, address="2-3-1 Asakusa, Taito", duration=90, price=0, currency="JPY", description="Templo budista mais antigo de Tóquio com portão Kaminarimon e mercado Nakamise", indoor=False, base_score=0.96),
        _a(name="Tsukiji Outer Market", category="restaurant", tags=["food", "gastronomy", "culture"], lat=35.6654, lng=139.7707, address="4-16-2 Tsukiji, Chuo", duration=120, price=3000, currency="JPY", description="Sushi fresco, tamagoyaki e street food no mercado exterior histórico", indoor=False, base_score=0.93),
        _a(name="TeamLab Borderless", category="museum", tags=["art", "culture", "photography"], lat=35.6264, lng=139.7837, address="Azabudai Hills, Minato", duration=150, price=3800, currency="JPY", description="Museu de arte digital imersiva — instalações de luz infinitas", indoor=True, requires_booking=True, base_score=0.94),
        _a(name="Meiji Shrine", category="tour", tags=["history", "religion", "nature"], lat=35.6764, lng=139.6993, address="1-1 Yoyogikamizonocho, Shibuya", duration=60, price=0, currency="JPY", description="Santuário xintoísta em floresta de 70 hectares no coração de Shibuya", indoor=False, base_score=0.91),
        _a(name="Shibuya Crossing", category="tour", tags=["photography", "culture"], lat=35.6595, lng=139.7004, address="Shibuya, Shibuya", duration=30, price=0, currency="JPY", description="O cruzamento mais movimentado do mundo — caos organizado e luzes de néon", indoor=False, base_score=0.88),
        _a(name="Shinjuku Gyoen", category="nature", tags=["nature", "photography", "wellness"], lat=35.6852, lng=139.7100, address="11 Naitomachi, Shinjuku", duration=120, price=500, currency="JPY", description="Jardim com 20.000 árvores — paisagismo japonês, francês e inglês", indoor=False, base_score=0.89),
        _a(name="Golden Gai", category="nightlife", tags=["nightlife", "culture", "food"], lat=35.6938, lng=139.7036, address="1 Chome Kabukicho, Shinjuku", duration=180, price=2000, currency="JPY", description="Seis becos minúsculos com 200+ bares de 6 lugares — cada um com personalidade única", indoor=True, base_score=0.87),
        _a(name="Akihabara Electric Town", category="shopping", tags=["shopping", "culture"], lat=35.7023, lng=139.7745, address="Sotokanda, Chiyoda", duration=150, price=0, currency="JPY", description="Meca da cultura otaku — eletrônicos, mangá, arcades e maid cafés", indoor=True, base_score=0.83),
        _a(name="Ramen Street (Tokyo Station)", category="restaurant", tags=["food", "gastronomy"], lat=35.6812, lng=139.7671, address="Tokyo Station B1F, Chiyoda", duration=60, price=1200, currency="JPY", description="Oito dos melhores ramen shops do Japão sob a estação central", indoor=True, base_score=0.85),
    ],
    "london": [
        _a(name="British Museum", category="museum", tags=["history", "culture", "art"], lat=51.5194, lng=-0.1270, address="Great Russell St, Bloomsbury", duration=180, price=0, currency="GBP", description="Pedra de Roseta, múmias e 8 milhões de artefatos — entrada gratuita", indoor=True, base_score=0.96),
        _a(name="Tower of London", category="museum", tags=["history", "culture", "architecture"], lat=51.5081, lng=-0.0759, address="London EC3N 4AB", duration=150, price=33, currency="GBP", description="Fortaleza medieval com as Crown Jewels e 900 anos de história", indoor=False, requires_booking=True, base_score=0.94),
        _a(name="Borough Market", category="restaurant", tags=["food", "gastronomy", "culture"], lat=51.5055, lng=-0.0910, address="8 Southwark St, SE1", duration=120, price=0, currency="GBP", description="O mercado de comida mais antigo de Londres — queijos, pães e street food global", indoor=False, base_score=0.92),
        _a(name="Hyde Park", category="nature", tags=["nature", "wellness", "sports"], lat=51.5073, lng=-0.1657, address="Hyde Park, London W2", duration=120, price=0, currency="GBP", description="142 hectares de verde real — Serpentine Lake, Diana Memorial e Speaker's Corner", indoor=False, base_score=0.88),
        _a(name="Camden Market", category="shopping", tags=["shopping", "food", "culture"], lat=51.5413, lng=-0.1470, address="Camden Lock Place, NW1", duration=150, price=0, currency="GBP", description="Mercado alternativo com comida do mundo, vintage e arte independente", indoor=False, base_score=0.85),
        _a(name="West End Show", category="nightlife", tags=["culture", "music", "nightlife"], lat=51.5115, lng=-0.1285, address="Shaftesbury Avenue, W1D", duration=150, price=55, currency="GBP", description="Distrito teatral com musicais de classe mundial — Les Mis, Hamilton, Wicked", indoor=True, requires_booking=True, base_score=0.90),
        _a(name="Tate Modern", category="museum", tags=["art", "culture", "architecture"], lat=51.5076, lng=-0.0994, address="Bankside, SE1 9TG", duration=120, price=0, currency="GBP", description="Arte moderna e contemporânea em uma usina elétrica convertida às margens do Tâmisa", indoor=True, base_score=0.91),
        _a(name="Thames River Cruise", category="tour", tags=["photography", "history"], lat=51.5024, lng=-0.1188, address="Westminster Pier, SW1A", duration=90, price=18, currency="GBP", description="Cruzeiro de Westminster a Greenwich passando pela Tower Bridge e Canary Wharf", indoor=False, base_score=0.84),
    ],
}

# ---------------------------------------------------------------------------
# Seasonal events
# ---------------------------------------------------------------------------

_SeasonalEvent = dict[str, Any]

_SEASONAL_EVENTS: list[_SeasonalEvent] = [
    {"city": "rio de janeiro", "month_start": 2, "month_end": 3, "name": "Carnaval do Rio", "category": "tour", "tags": ["culture", "music", "nightlife"], "lat": -22.9121, "lng": -43.2302, "address": "Sambódromo, Centro", "duration": 300, "price": 200, "currency": "BRL", "indoor": False, "requires_booking": True, "description": "O maior espetáculo da Terra — desfiles das escolas de samba no Sambódromo", "base_score": 0.99},
    {"city": "rio de janeiro", "month_start": 12, "month_end": 1, "name": "Réveillon de Copacabana", "category": "tour", "tags": ["culture", "nightlife", "beach"], "lat": -22.9711, "lng": -43.1822, "address": "Praia de Copacabana", "duration": 300, "price": 0, "currency": "BRL", "indoor": False, "requires_booking": False, "description": "Queima de fogos épica na virada do ano com 2 milhões de pessoas de branco", "base_score": 0.97},
    {"city": "são paulo", "month_start": 6, "month_end": 6, "name": "Festa Junina — Arraial", "category": "tour", "tags": ["food", "culture", "music"], "lat": -23.5455, "lng": -46.6388, "address": "Vários locais, Centro", "duration": 180, "price": 0, "currency": "BRL", "indoor": False, "requires_booking": False, "description": "Quadrilha, quentão e paçoca: as festas juninas tomam conta de São Paulo", "base_score": 0.85},
    {"city": "paris", "month_start": 7, "month_end": 7, "name": "Fête Nationale (14 Juillet)", "category": "tour", "tags": ["culture", "history"], "lat": 48.8584, "lng": 2.2945, "address": "Champ de Mars", "duration": 180, "price": 0, "currency": "EUR", "indoor": False, "requires_booking": False, "description": "Fogos de artifício na Torre Eiffel e desfile militar nos Champs-Élysées", "base_score": 0.93},
    {"city": "paris", "month_start": 12, "month_end": 12, "name": "Marché de Noël", "category": "shopping", "tags": ["shopping", "food", "culture"], "lat": 48.8656, "lng=": 2.3212, "lng": 2.3212, "address": "Jardin des Tuileries", "duration": 120, "price": 0, "currency": "EUR", "indoor": False, "requires_booking": False, "description": "Mercados de Natal com vin chaud, raclette e artesanato ao longo das Tuileries", "base_score": 0.88},
    {"city": "tokyo", "month_start": 3, "month_end": 4, "name": "Hanami — Cherry Blossom", "category": "nature", "tags": ["nature", "photography", "culture"], "lat": 35.6852, "lng": 139.7100, "address": "Shinjuku Gyoen & Ueno Park", "duration": 180, "price": 0, "currency": "JPY", "indoor": False, "requires_booking": False, "description": "Piquenique sob cerejeiras em flor — a tradição mais bonita do Japão", "base_score": 0.97},
    {"city": "lisbon", "month_start": 6, "month_end": 6, "name": "Festas de Santo António", "category": "tour", "tags": ["culture", "food", "music", "nightlife"], "lat": 38.7114, "lng": -9.1300, "address": "Alfama", "duration": 240, "price": 0, "currency": "EUR", "indoor": False, "requires_booking": False, "description": "Sardinhas grelhadas, manjerico e marchas populares na noite mais quente de Lisboa", "base_score": 0.93},
    {"city": "london", "month_start": 11, "month_end": 12, "name": "Winter Wonderland", "category": "tour", "tags": ["shopping", "culture", "food"], "lat": 51.5073, "lng": -0.1657, "address": "Hyde Park", "duration": 180, "price": 0, "currency": "GBP", "indoor": False, "requires_booking": False, "description": "Mercado de Natal, pista de gelo e roda-gigante no Hyde Park", "base_score": 0.87},
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_seasonal_events(
    destination: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Return seasonal events at *destination* that overlap with the travel dates.

    Unlike ``discover_activities`` this returns lightweight event metadata
    suitable for destination analysis, not full Activity TypedDicts.

    Returns:
        List of dicts with keys: name, category, description, month_start, month_end.
    """
    key = destination.lower().strip()
    start = datetime.date.fromisoformat(start_date)
    end = datetime.date.fromisoformat(end_date)

    matching: list[dict[str, Any]] = []
    for evt in _SEASONAL_EVENTS:
        if evt["city"] != key:
            continue
        for d in _date_range(start, end):
            if _month_in_range(d.month, evt["month_start"], evt["month_end"]):
                matching.append({
                    "name": evt["name"],
                    "category": evt["category"],
                    "description": evt["description"],
                    "month_start": evt["month_start"],
                    "month_end": evt["month_end"],
                })
                break  # each event at most once
    return matching


def _seed_for(destination: str, extra: str = "") -> int:
    raw = f"{destination.lower().strip()}:{extra}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16)


def _month_in_range(month: int, start: int, end: int) -> bool:
    """Check if month falls within [start, end], wrapping around December→January."""
    if start <= end:
        return start <= month <= end
    return month >= start or month <= end


def discover_activities(
    destination: str,
    interests: list[str],
    start_date: str,
    end_date: str,
    budget_per_day: float,
    max_results: int = 50,
) -> list[Activity]:
    """Return scored and filtered activities for the given destination.

    Deterministic: same inputs always produce the same output list.

    Args:
        destination: City name (case-insensitive).
        interests: Traveler interest tags (e.g. ``["history", "food"]``).
        start_date: ISO date ``YYYY-MM-DD``.
        end_date: ISO date ``YYYY-MM-DD``.
        budget_per_day: Max price per activity (same currency as activity).
        max_results: Cap on returned activities.
    """
    key = destination.lower().strip()
    pool = list(_ACTIVITIES_DB.get(key, []))

    start = datetime.date.fromisoformat(start_date)
    end = datetime.date.fromisoformat(end_date)

    # Inject seasonal events that overlap with the travel dates
    for evt in _SEASONAL_EVENTS:
        if evt["city"] != key:
            continue
        for d in _date_range(start, end):
            if _month_in_range(d.month, evt["month_start"], evt["month_end"]):
                pool.append(
                    _a(
                        name=evt["name"],
                        category=evt["category"],
                        tags=evt["tags"],
                        lat=evt["lat"],
                        lng=evt["lng"],
                        address=evt["address"],
                        duration=evt["duration"],
                        price=evt["price"],
                        currency=evt["currency"],
                        indoor=evt["indoor"],
                        requires_booking=evt["requires_booking"],
                        description=evt["description"],
                        base_score=evt["base_score"],
                    )
                )
                break  # add each event at most once

    # Climate-aware: check if beach/outdoor activities make sense
    mid_month = start.month
    lat = _get_lat(key)
    warm = _is_warm_season(mid_month, lat)

    # Resolve interest → categories
    matched_categories: set[str] = set()
    for interest in interests:
        matched_categories.update(INTEREST_TO_CATEGORIES.get(interest.lower(), []))

    rng = random.Random(_seed_for(destination, f"{start_date}:{end_date}"))

    # Score each activity
    scored: list[tuple[float, RawEntry]] = []
    for entry in pool:
        # Budget filter
        if entry["price"] > budget_per_day and entry["price"] > 0:
            continue

        # Climate filter: skip beach if cold
        if not warm and "beach" in entry["tags"]:
            continue

        # Interest-match boost
        tag_set = set(entry["tags"])
        interest_set = set(i.lower() for i in interests)
        tag_overlap = len(tag_set & interest_set)
        category_match = 1.0 if entry["category"] in matched_categories else 0.0

        # Composite score
        relevance = min(tag_overlap / max(len(interest_set), 1), 1.0)
        score = (
            0.40 * entry["base_score"]
            + 0.35 * relevance
            + 0.15 * category_match
            + 0.10 * rng.random()  # small jitter for variety
        )
        scored.append((score, entry))

    scored.sort(key=lambda t: t[0], reverse=True)

    # Category diversity: cap per category
    category_counts: dict[str, int] = {}
    max_per_category = max(max_results // 4, 3)
    diverse: list[tuple[float, RawEntry]] = []

    for score, entry in scored:
        cat = entry["category"]
        count = category_counts.get(cat, 0)
        if count < max_per_category:
            diverse.append((score, entry))
            category_counts[cat] = count + 1
        if len(diverse) >= max_results:
            break

    # Convert to Activity TypedDicts
    results: list[Activity] = []
    for idx, (score, entry) in enumerate(diverse):
        hours = dict(_HOURS_BY_CATEGORY.get(entry["category"], _TOUR_HOURS))
        results.append(
            Activity(
                id=f"act-{key[:3]}-{idx:03d}",
                name=entry["name"],
                category=entry["category"],
                address=entry["address"],
                coordinates={"lat": entry["lat"], "lng": entry["lng"]},
                duration_minutes=entry["duration"],
                price=entry["price"],
                currency=entry["currency"],
                opening_hours=hours,
                requires_booking=entry["requires_booking"],
                indoor=entry["indoor"],
                description=entry["description"],
                score=round(score, 4),
            )
        )

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CITY_LATS: dict[str, float] = {
    "rio de janeiro": -22.91,
    "são paulo": -23.55,
    "paris": 48.86,
    "lisbon": 38.72,
    "tokyo": 35.68,
    "london": 51.51,
}


def _get_lat(city: str) -> float:
    return _CITY_LATS.get(city, 45.0)


def _is_warm_season(month: int, lat: float) -> bool:
    if lat >= 0:
        return month in (4, 5, 6, 7, 8, 9)
    return month in (10, 11, 12, 1, 2, 3)


def _date_range(
    start: datetime.date, end: datetime.date
) -> list[datetime.date]:
    days: list[datetime.date] = []
    current = start
    while current <= end:
        days.append(current)
        current += datetime.timedelta(days=1)
    return days
