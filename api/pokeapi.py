import requests
import logging

class PokeAPI:
    BASE_URL = "https://pokeapi.co/api/v2"

    def __init__(self):
        # Cache responses to avoid rate limiting
        self._cache = {}

    def get_pokemon(self, pokemon_id_or_name):
        key = str(pokemon_id_or_name).lower()
        if key in self._cache:
            return self._cache[key]
        
        try:
            url = f"{self.BASE_URL}/pokemon/{key}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                result = {
                    'name': data['name'].capitalize(),
                    'sprite': data['sprites']['front_default'],
                    'types': [t['type']['name'] for t in data['types']]
                }
                self._cache[key] = result
                return result
        except requests.RequestException as e:
            logging.error(f"PokeAPI fetch failed: {e}")
        
        return None
