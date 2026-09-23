---
title: "Documentation - PokéAPI"
source: "https://pokeapi.co/docs/v2"
author:
published:
created: 2026-05-07
description: "An open RESTful API for Pokémon data"
tags:
  - "clippings"
---
If you were using v1 of this API, please switch to v2 (this page). [Read more…](https://pokeapi.co/docs/v1)

**Quick tip:** Use your browser's "find on page" feature to search for specific resource types (Ctrl+F or Cmd+F).

## Information

This is a **consumption-only** API — only the HTTP GET method is available on resources.

No authentication is required to access this API, and all resources are fully open and available. Since the move to static hosting in November 2018, rate limiting has been removed entirely, but we still encourage you to limit the frequency of requests to limit our hosting costs.

## Fair Use Policy

PokéAPI is free and open to use. It is also very popular. Because of this, we ask every developer to abide by our fair use policy. People not complying with the fair use policy will have their IP address permanently banned.

PokéAPI is primarily an educational tool, and we will not tolerate denial of service attacks preventing people from learning.

Rules:

- Locally cache resources whenever you request them.
- Be nice and friendly to your fellow PokéAPI developers.
- If you spot security vulnerabilities act and [report them](https://github.com/PokeAPI/pokeapi/blob/master/SECURITY.md#reporting-a-vulnerability) responsibly.

## Slack and community

Currently no maintainer has enough free time to support the community on Slack. Our Slack is in an unmaintained status. You can still sign up right [here](https://join.slack.com/t/pokeapi/shared_invite/zt-2ampo6her-_tHSI3uOS65WzGypt7Y96w) then visit our [Slack](https://pokeapi.slack.com/) page.

## Wrapper Libraries

- **Node Server-side with auto caching**: [Pokedex Promise v2](https://github.com/PokeAPI/pokedex-promise-v2) by Thomas Asadurian and Alessandro Pezzé
- **Browser-side with auto caching**: [pokeapi-js-wrapper](https://github.com/PokeAPI/pokeapi-js-wrapper) by Alessandro Pezzé
- **Python 3 with auto caching**: [PokeBase](https://github.com/GregHilmes/pokebase) by Greg Hilmes
- **Python 2/3 with auto caching**: [Pokepy](https://github.com/PokeAPI/pokepy) by Paul Hallett
- **Kotlin Multiplatform (JVM, Native, Browser, and Node) with auto caching**: [PokeKotlin](https://github.com/PokeAPI/pokekotlin) by sargunv
- **Java (Spring Boot) with auto caching**: [pokeapi-reactor](https://github.com/SirSkaro/pokeapi-reactor) by Benjamin Churchill
- **.NET (C#, VB, etc)**: [PokeApi.NET](https://gitlab.com/PoroCYon/PokeApi.NET) by PoroCYon
- **.NET Standard**: [PokeApiNet](https://github.com/mtrdp642/PokeApiNet) by mtrdp642
- **Swift**: [PokemonAPI](https://github.com/kinkofer/PokemonAPI) by kinkofer
- **PHP**: [PokePHP](https://github.com/danrovito/pokephp) by Dan Rovito
- **PHP**: [PHPokéAPI](https://github.com/lmerotta/phpokeapi) by lmerotta
- **Ruby**: [Poke-Api-V2](https://github.com/rdavid1099/poke-api-v2) by rdavid1099
- **Go**: [pokeapi-go](https://github.com/mtslzr/pokeapi-go) by mtslzr
- **Go**: [PokeGo](https://github.com/JoshGuarino/PokeGo) by Josh Guarino
- **Crystal**: [pokeapi](https://github.com/henrikac/pokeapi) by henrikac
- **Typescript with auto caching**: [Pokenode-ts](https://github.com/Gabb-c/pokenode-ts) by Gabb-c
- **Rust with auto caching**: [Rustemon](https://crates.io/crates/rustemon) by mlemesle
- **Asynchronous Python wrapper with auto caching**: [aiopokeapi](https://github.com/beastmatser/aiopokeapi) by beastmatser
- **Scala 3 with auto caching**: [pokeapi-scala](https://github.com/juliano/pokeapi-scala) by Juliano Alves
- **Elixir wrapper with auto caching**: [Max-Elixir-PokeAPI](https://github.com/HenriqueArtur/Max-Elixir-PokeAPI) by Henrique Artur

## Resource Lists/Pagination (group)

Calling any API endpoint without a resource ID or name will return a paginated list of available resources for that API. By default, a list "page" will contain up to 20 resources. If you would like to change this just add a 'limit' query parameter to the GET request, e.g. `?limit=60`. You can use 'offset' to move to the next page, e.g. `?limit=60&offset=60`. `characteristic`, `contest-effect`, `evolution-chain`, `machine`, `super-contest-effect` endpoints are unnamed, the rest are named.

### Named (endpoint)

GET https://pokeapi.co/api/v2/{endpoint}/

- - 248
		- "https://pokeapi.co/api/v2/ability/?limit=20&offset=20"
		- null
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "stench"
						- "https://pokeapi.co/api/v2/ability/1/"

#### NamedAPIResourceList (type)

| Name | Description | Type |
| --- | --- | --- |
| count | The total number of resources available from this API. | *integer* |
| next | The URL for the next page in the list. | *string* |
| previous | The URL for the previous page in the list. | *string* |
| results | A list of named API resources. | list *[NamedAPIResource](#namedapiresource)* |

### Unnamed (endpoint)

GET https://pokeapi.co/api/v2/{endpoint}/

- - 541
		- "https://pokeapi.co/api/v2/evolution-chain?offset=20&limit=20"
		- null
		- ▶
		\[\] 1 item
		- ▶
			{} 1 key
			- "https://pokeapi.co/api/v2/evolution-chain/1/"

#### APIResourceList (type)

| Name | Description | Type |
| --- | --- | --- |
| count | The total number of resources available from this API. | *integer* |
| next | The URL for the next page in the list. | *string* |
| previous | The URL for the previous page in the list. | *string* |
| results | A list of unnamed API resources. | list *[APIResource](#apiresource)* |

## Berries (group)

### Berries (endpoint)

Berries are small fruits that can provide HP and status condition restoration, stat enhancement, and even damage negation when eaten by Pokémon. Check out [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Berry) for greater detail.

GET https://pokeapi.co/api/v2/berry/{id or name}/

- - 1
		- "cheri"
		- 3
		- 5
		- 60
		- 20
		- 25
		- 15
		- ▶
		{} 2 keys
		- "soft"
				- "https://pokeapi.co/api/v2/berry-firmness/2/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- 10
						- ▶
				{} 2 keys
				- "spicy"
								- "https://pokeapi.co/api/v2/berry-flavor/1/"
		- ▶
		{} 2 keys
		- "cheri-berry"
				- "https://pokeapi.co/api/v2/item/126/"
		- ▶
		{} 2 keys
		- "fire"
				- "https://pokeapi.co/api/v2/type/10/"

#### Berry (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| growth\_time | Time it takes the tree to grow one stage, in hours. Berry trees go through four of these growth stages before they can be picked. | *integer* |
| max\_harvest | The maximum number of these berries that can grow on one tree in Generation IV. | *integer* |
| natural\_gift\_power | The power of the move "Natural Gift" when used with this Berry. | *integer* |
| size | The size of this Berry, in millimeters. | *integer* |
| smoothness | The smoothness of this Berry, used in making Pokéblocks or Poffins. | *integer* |
| soil\_dryness | The speed at which this Berry dries out the soil as it grows. A higher rate means the soil dries more quickly. | *integer* |
| firmness | The firmness of this berry, used in making Pokéblocks or Poffins. | *[NamedAPIResource](#namedapiresource)* (*[BerryFirmness](#berryfirmness)*) |
| flavors | A list of references to each flavor a berry can have and the potency of each of those flavors in regard to this berry. | list *[BerryFlavorMap](#berryflavormap)* |
| item | Berries are actually items. This is a reference to the item specific data for this berry. | *[NamedAPIResource](#namedapiresource)* (*[Item](#item)*) |
| natural\_gift\_type | The type inherited by "Natural Gift" when used with this Berry. | *[NamedAPIResource](#namedapiresource)* (*[Type](#type)*) |

#### BerryFlavorMap (type)

| Name | Description | Type |
| --- | --- | --- |
| potency | How powerful the referenced flavor is for this berry. | *integer* |
| flavor | The referenced berry flavor. | *[NamedAPIResource](#namedapiresource)* (*[BerryFlavor](#berryflavor)*) |

### Berry Firmnesses (endpoint)

Berries can be soft or hard. Check out [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Category:Berries_by_firmness) for greater detail.

GET https://pokeapi.co/api/v2/berry-firmness/{id or name}/

- - 1
		- "very-soft"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "pecha"
						- "https://pokeapi.co/api/v2/berry/3/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Very Soft"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"

#### BerryFirmness (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| berries | A list of the berries with this firmness. | list **[NamedAPIResource](#namedapiresource)* (*[Berry](#berry)*)* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |

### Berry Flavors (endpoint)

Flavors determine whether a Pokémon will benefit or suffer from eating a berry based on their [nature](#natures). Check out [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Flavor) for greater detail.

GET https://pokeapi.co/api/v2/berry-flavor/{id or name}/

- - 1
		- "spicy"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- 10
						- ▶
				{} 2 keys
				- "rowap"
								- "https://pokeapi.co/api/v2/berry/64/"
		- ▶
		{} 2 keys
		- "cool"
				- "https://pokeapi.co/api/v2/contest-type/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Spicy"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"

#### BerryFlavor (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| berries | A list of the berries with this flavor. | list *[FlavorBerryMap](#flavorberrymap)* |
| contest\_type | The contest type that correlates with this berry flavor. | *[NamedAPIResource](#namedapiresource)* (*[ContestType](#contesttype)*) |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |

#### FlavorBerryMap (type)

| Name | Description | Type |
| --- | --- | --- |
| potency | How powerful the referenced flavor is for this berry. | *integer* |
| berry | The berry with the referenced flavor. | *[NamedAPIResource](#namedapiresource)* (*[Berry](#berry)*) |

## Contests (group)

### Contest Types (endpoint)

Contest types are categories judges used to weigh a Pokémon's condition in Pokémon contests. Check out [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Contest_condition) for greater detail.

GET https://pokeapi.co/api/v2/contest-type/{id or name}/

- - 1
		- "cool"
		- ▶
		{} 2 keys
		- "spicy"
				- "https://pokeapi.co/api/v2/berry-flavor/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 3 keys
			- "Cool"
						- "Red"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"

#### ContestType (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| berry\_flavor | The berry flavor that correlates with this contest type. | *[NamedAPIResource](#namedapiresource)* (*[BerryFlavor](#berryflavor)*) |
| names | The name of this contest type listed in different languages. | list *[ContestName](#contestname)* |

#### ContestName (type)

| Name | Description | Type |
| --- | --- | --- |
| name | The name for this contest. | *string* |
| color | The color associated with this contest's name. | *string* |
| language | The language that this name is in. | *[NamedAPIResource](#namedapiresource)* (*[Language](#language)*) |

### Contest Effects (endpoint)

Contest effects refer to the effects of moves when used in contests.

GET https://pokeapi.co/api/v2/contest-effect/{id}/

- - 1
		- 4
		- 0
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Gives a high number of appeal points wth no other effects."
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "A highly appealing move."
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"

#### ContestEffect (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| appeal | The base number of hearts the user of this move gets. | *integer* |
| jam | The base number of hearts the user's opponent loses. | *integer* |
| effect\_entries | The result of this contest effect listed in different languages. | list *[Effect](#effect)* |
| flavor\_text\_entries | The flavor text of this contest effect listed in different languages. | list *[ContestEffectFlavorText](#contesteffectflavortext)* |

#### ContestEffectFlavorText (type)

| Name | Description | Type |
| --- | --- | --- |
| flavor\_text | The localized flavor text for an API resource in a specific language. | *string* |
| language | The language this name is in. | *[NamedAPIResource](#namedapiresource)* (*[Language](#language)*) |

### Super Contest Effects (endpoint)

Super contest effects refer to the effects of moves when used in super contests.

GET https://pokeapi.co/api/v2/super-contest-effect/{id}/

- - 1
		- 2
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Enables the user to perform first in the next turn."
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "agility"
						- "https://pokeapi.co/api/v2/move/97/"

#### SuperContestEffect (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| appeal | The level of appeal this super contest effect has. | *integer* |
| flavor\_text\_entries | The flavor text of this super contest effect listed in different languages. | list *[SuperContestEffectFlavorText](#supercontesteffectflavortext)* |
| moves | A list of moves that have the effect when used in super contests. | list **[NamedAPIResource](#namedapiresource)* (*[Move](#move)*)* |

#### SuperContestEffectFlavorText (type)

| Name | Description | Type |
| --- | --- | --- |
| flavor\_text | The localized flavor text for an API resource in a specific language. | *string* |
| language | The language this name is in. | *[NamedAPIResource](#namedapiresource)* (*[Language](#language)*) |

## Encounters (group)

### Encounter Methods (endpoint)

Methods by which the player might can encounter Pokémon in the wild, e.g., walking in tall grass. Check out [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Wild_Pok%C3%A9mon) for greater detail.

GET https://pokeapi.co/api/v2/encounter-method/{id or name}/

- - 1
		- "walk"
		- 1
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Walking in tall grass or a cave"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"

#### EncounterMethod (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| order | A good value for sorting. | *integer* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |

### Encounter Conditions (endpoint)

Conditions which affect what pokemon might appear in the wild, e.g., day or night.

GET https://pokeapi.co/api/v2/encounter-condition/{id or name}/

- - 1
		- "swarm"
		- ▶
		\[\] 2 items
		- ▶
			{} 2 keys
			- "swarm-yes"
						- "https://pokeapi.co/api/v2/encounter-condition-value/1/"
				- ▶
			{} 2 keys
			- "swarm-no"
						- "https://pokeapi.co/api/v2/encounter-condition-value/2/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Schwarm"
						- ▶
				{} 2 keys
				- "de"
								- "https://pokeapi.co/api/v2/language/6/"

#### EncounterCondition (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| values | A list of possible values for this encounter condition. | list **[NamedAPIResource](#namedapiresource)* (*[EncounterConditionValue](#encounterconditionvalue)*)* |

### Encounter Condition Values (endpoint)

Encounter condition values are the various states that an encounter condition can have, i.e., time of day can be either day or night.

GET https://pokeapi.co/api/v2/encounter-condition-value/{id or name}/

- - 1
		- "swarm-yes"
		- ▶
		{} 2 keys
		- "swarm"
				- "https://pokeapi.co/api/v2/encounter-condition/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "WÃ¤hrend eines Schwarms"
						- ▶
				{} 2 keys
				- "de"
								- "https://pokeapi.co/api/v2/language/6/"

#### EncounterConditionValue (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| condition | The condition this encounter condition value pertains to. | *[NamedAPIResource](#namedapiresource)* (*[EncounterCondition](#encountercondition)*) |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |

## Evolution (group)

### Evolution Chains (endpoint)

Evolution chains are essentially family trees. They start with the lowest stage within a family and detail evolution conditions for each as well as Pokémon they can evolve into up through the hierarchy.

GET https://pokeapi.co/api/v2/evolution-chain/{id}/

- - 7
		- null
		- ▶
		{} 4 keys

#### EvolutionChain (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| baby\_trigger\_item | The item that a Pokémon would be holding when mating that would trigger the egg hatching a baby Pokémon rather than a basic Pokémon. | *[NamedAPIResource](#namedapiresource)* (*[Item](#item)*) |
| chain | The base chain link object. Each link contains evolution details for a Pokémon in the chain. Each link references the next Pokémon in the natural evolution order. | [ChainLink](#chainlink) |

#### ChainLink (type)

| Name | Description | Type |
| --- | --- | --- |
| is\_baby | Whether or not this link is for a baby Pokémon. This would only ever be true on the base link. | *boolean* |
| species | The Pokémon species at this point in the evolution chain. | *[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*) |
| evolution\_details | All details regarding the specific details of the referenced Pokémon species evolution. | list *[EvolutionDetail](#evolutiondetail)* |
| evolves\_to | A List of chain objects. | list *[ChainLink](#chainlink)* |

#### EvolutionDetail (type)

| Name | Description | Type |
| --- | --- | --- |
| item | The item required to cause evolution this into Pokémon species. | *[NamedAPIResource](#namedapiresource)* (*[Item](#item)*) |
| trigger | The type of event that triggers evolution into this Pokémon species. | *[NamedAPIResource](#namedapiresource)* (*[EvolutionTrigger](#evolutiontrigger)*) |
| gender | The id of the gender of the evolving Pokémon species must be in order to evolve into this Pokémon species. | *integer* |
| held\_item | The item the evolving Pokémon species must be holding during the evolution trigger event to evolve into this Pokémon species. | *[NamedAPIResource](#namedapiresource)* (*[Item](#item)*) |
| known\_move | The move that must be known by the evolving Pokémon species during the evolution trigger event in order to evolve into this Pokémon species. | *[NamedAPIResource](#namedapiresource)* (*[Move](#move)*) |
| known\_move\_type | The evolving Pokémon species must know a move with this type during the evolution trigger event in order to evolve into this Pokémon species. | *[NamedAPIResource](#namedapiresource)* (*[Type](#type)*) |
| location | The location the evolution must be triggered at. | *[NamedAPIResource](#namedapiresource)* (*[Location](#location)*) |
| min\_level | The minimum required level of the evolving Pokémon species to evolve into this Pokémon species. | *integer* |
| min\_happiness | The minimum required level of happiness the evolving Pokémon species to evolve into this Pokémon species. | *integer* |
| min\_beauty | The minimum required level of beauty the evolving Pokémon species to evolve into this Pokémon species. | *integer* |
| min\_affection | The minimum required level of affection the evolving Pokémon species to evolve into this Pokémon species. | *integer* |
| needs\_multiplayer | Whether or not multiplayer link play is needed to evolve into this Pokémon species (e.g. Union Circle). | *boolean* |
| needs\_overworld\_rain | Whether or not it must be raining in the overworld to cause evolution this Pokémon species. | *boolean* |
| party\_species | The Pokémon species that must be in the players party in order for the evolving Pokémon species to evolve into this Pokémon species. | *[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*) |
| party\_type | The player must have a Pokémon of this type in their party during the evolution trigger event in order for the evolving Pokémon species to evolve into this Pokémon species. | *[NamedAPIResource](#namedapiresource)* (*[Type](#type)*) |
| relative\_physical\_stats | The required relation between the Pokémon's Attack and Defense stats. 1 means Attack > Defense. 0 means Attack = Defense. -1 means Attack < Defense. | *integer* |
| time\_of\_day | The required time of day. Day or night. | *string* |
| trade\_species | Pokémon species for which this one must be traded. | *[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*) |
| turn\_upside\_down | Whether or not the 3DS needs to be turned upside-down as this Pokémon levels up. | *boolean* |
| region | The required region in which this evolution can occur. | *[NamedAPIResource](#namedapiresource)* (*[Region](#region)*) |
| base\_form | The required form for which this evolution can occur. | *[NamedAPIResource](#namedapiresource)* (*[Pokemon](#pokemon)*) |
| used\_move | The move that must be used by the evolving Pokémon species during the evolution trigger event in order to evolve into this Pokémon species. | *[NamedAPIResource](#namedapiresource)* (*[Move](#move)*) |
| min\_move\_count | The minimum number of times a move must be used in order to evolve into this Pokémon species. | *integer* |
| min\_steps | The minimum number of steps that must be taken in order to evolve into this Pokémon species. | *integer* |
| min\_damage\_taken | The minimum amount of damage taken during the evolution trigger event in order to evolve into this Pokémon species. | *integer* |

### Evolution Triggers (endpoint)

Evolution triggers are the events and conditions that cause a Pokémon to evolve. Check out [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Methods_of_evolution) for greater detail.

GET https://pokeapi.co/api/v2/evolution-trigger/{id or name}/

- - 1
		- "level-up"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Level up"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "ivysaur"
						- "https://pokeapi.co/api/v2/pokemon-species/2/"

#### EvolutionTrigger (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| pokemon\_species | A list of pokemon species that result from this evolution trigger. | list **[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*)* |

## Games (group)

### Generations (endpoint)

A generation is a grouping of the Pokémon games that separates them based on the Pokémon they include. In each generation, a new set of Pokémon, Moves, Abilities and Types that did not exist in the previous generation are released.

GET https://pokeapi.co/api/v2/generation/{id or name}/

- - 1
		- "generation-i"
		- \[\] 0 items
		- ▶
		{} 2 keys
		- "kanto"
				- "https://pokeapi.co/api/v2/region/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "pound"
						- "https://pokeapi.co/api/v2/move/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Generation I"
						- ▶
				{} 2 keys
				- "de"
								- "https://pokeapi.co/api/v2/language/6/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "bulbasaur"
						- "https://pokeapi.co/api/v2/pokemon-species/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "normal"
						- "https://pokeapi.co/api/v2/type/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "red-blue"
						- "https://pokeapi.co/api/v2/version-group/1/"

#### Generation (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| abilities | A list of abilities that were introduced in this generation. | list **[NamedAPIResource](#namedapiresource)* (*[Ability](#ability)*)* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| main\_region | The main region travelled in this generation. | *[NamedAPIResource](#namedapiresource)* (*[Region](#region)*) |
| moves | A list of moves that were introduced in this generation. | list **[NamedAPIResource](#namedapiresource)* (*[Move](#move)*)* |
| pokemon\_species | A list of Pokémon species that were introduced in this generation. | list **[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*)* |
| types | A list of types that were introduced in this generation. | list **[NamedAPIResource](#namedapiresource)* (*[Type](#type)*)* |
| version\_groups | A list of version groups that were introduced in this generation. | list **[NamedAPIResource](#namedapiresource)* (*[VersionGroup](#versiongroup)*)* |

### Pokedexes (endpoint)

A Pokédex is a handheld electronic encyclopedia device; one which is capable of recording and retaining information of the various Pokémon in a given region with the exception of the national dex and some smaller dexes related to portions of a region. See [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Pokedex) for greater detail.

GET https://pokeapi.co/api/v2/pokedex/{id or name}/

- - 2
		- "kanto"
		- true
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Rot/Blau/Gelb Kanto Dex"
						- ▶
				{} 2 keys
				- "de"
								- "https://pokeapi.co/api/v2/language/6/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Kanto"
						- ▶
				{} 2 keys
				- "de"
								- "https://pokeapi.co/api/v2/language/6/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- 1
						- ▶
				{} 2 keys
				- "bulbasaur"
								- "https://pokeapi.co/api/v2/pokemon-species/1/"
		- ▶
		{} 2 keys
		- "kanto"
				- "https://pokeapi.co/api/v2/region/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "red-blue"
						- "https://pokeapi.co/api/v2/version-group/1/"

#### Pokedex (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| is\_main\_series | Whether or not this Pokédex originated in the main series of the video games. | *boolean* |
| descriptions | The description of this resource listed in different languages. | list *[Description](#description)* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| pokemon\_entries | A list of Pokémon catalogued in this Pokédex and their indexes. | list *[PokemonEntry](#pokemonentry)* |
| region | The region this Pokédex catalogues Pokémon for. | *[NamedAPIResource](#namedapiresource)* (*[Region](#region)*) |
| version\_groups | A list of version groups this Pokédex is relevant to. | list **[NamedAPIResource](#namedapiresource)* (*[VersionGroup](#versiongroup)*)* |

#### PokemonEntry (type)

| Name | Description | Type |
| --- | --- | --- |
| entry\_number | The index of this Pokémon species entry within the Pokédex. | *integer* |
| pokemon\_species | The Pokémon species being encountered. | *[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*) |

### Version (endpoint)

Versions of the games, e.g., Red, Blue or Yellow.

GET https://pokeapi.co/api/v2/version/{id or name}/

- - 1
		- "red"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Rot"
						- ▶
				{} 2 keys
				- "de"
								- "https://pokeapi.co/api/v2/language/6/"
		- ▶
		{} 2 keys
		- "red-blue"
				- "https://pokeapi.co/api/v2/version-group/1/"

#### Version (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| version\_group | The version group this version belongs to. | *[NamedAPIResource](#namedapiresource)* (*[VersionGroup](#versiongroup)*) |

### Version Groups (endpoint)

Version groups categorize highly similar versions of the games.

GET https://pokeapi.co/api/v2/version-group/{id or name}/

- - 1
		- "red-blue"
		- 1
		- ▶
		{} 2 keys
		- "generation-i"
				- "https://pokeapi.co/api/v2/generation/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "level-up"
						- "https://pokeapi.co/api/v2/move-learn-method/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "kanto"
						- "https://pokeapi.co/api/v2/pokedex/2/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "kanto"
						- "https://pokeapi.co/api/v2/region/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "red"
						- "https://pokeapi.co/api/v2/version/1/"

#### VersionGroup (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| order | Order for sorting. Almost by date of release, except similar versions are grouped together. | *integer* |
| generation | The generation this version was introduced in. | *[NamedAPIResource](#namedapiresource)* (*[Generation](#generation)*) |
| move\_learn\_methods | A list of methods in which Pokémon can learn moves in this version group. | list **[NamedAPIResource](#namedapiresource)* (*[MoveLearnMethod](#movelearnmethod)*)* |
| pokedexes | A list of Pokédexes introduces in this version group. | list **[NamedAPIResource](#namedapiresource)* (*[Pokedex](#pokedex)*)* |
| regions | A list of regions that can be visited in this version group. | list **[NamedAPIResource](#namedapiresource)* (*[Region](#region)*)* |
| versions | The versions this version group owns. | list **[NamedAPIResource](#namedapiresource)* (*[Version](#version)*)* |

## Items (group)

### Item (endpoint)

An item is an object in the games which the player can pick up, keep in their bag, and use in some manner. They have various uses, including healing, powering up, helping catch Pokémon, or to access a new area.

GET https://pokeapi.co/api/v2/item/{id or name}/

- - 1
		- "master-ball"
		- 0
		- 10
		- ▶
		{} 2 keys
		- "flinch"
				- "https://pokeapi.co/api/v2/item-fling-effect/7/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "holdable"
						- "https://pokeapi.co/api/v2/item-attribute/5/"
		- ▶
		{} 2 keys
		- "standard-balls"
				- "https://pokeapi.co/api/v2/item-category/34/"
		- ▶
		\[\] 1 item
		- ▶
			{} 3 keys
			- "Used in battle: \[Catches\]{mechanic:catch} a wild Pokémon without fail. If used in a trainer battle, nothing happens and the ball is lost."
						- "Catches a wild Pokémon every time."
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 3 keys
			- "The best Poké Ball with the ultimate level of performance. With it, you will catch any wild Pokémon without fail."
						- ▶
				{} 2 keys
				- "x-y"
								- "https://pokeapi.co/api/v2/version-group/15/"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- 1
						- ▶
				{} 2 keys
				- "generation-vi"
								- "https://pokeapi.co/api/v2/generation/6/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Master Ball"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		{} 1 key
		- "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/master-ball.png"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- ▶
				{} 2 keys
				- "chansey"
								- "https://pokeapi.co/api/v2/pokemon/113/"
						- ▶
				\[\] 1 item
		- ▶
		{} 1 key
		- "https://pokeapi.co/api/v2/evolution-chain/1/"

#### Item (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| cost | The price of this item in stores. | *integer* |
| fling\_power | The power of the move Fling when used with this item. | *integer* |
| fling\_effect | The effect of the move Fling when used with this item. | *[NamedAPIResource](#namedapiresource)* (*[ItemFlingEffect](#itemflingeffect)*) |
| attributes | A list of attributes this item has. | list **[NamedAPIResource](#namedapiresource)* (*[ItemAttribute](#itemattribute)*)* |
| category | The category of items this item falls into. | *[NamedAPIResource](#namedapiresource)* (*[ItemCategory](#itemcategory)*) |
| effect\_entries | The effect of this ability listed in different languages. | list *[VerboseEffect](#verboseeffect)* |
| flavor\_text\_entries | The flavor text of this ability listed in different languages. | list *[VersionGroupFlavorText](#versiongroupflavortext)* |
| game\_indices | A list of game indices relevent to this item by generation. | list *[GenerationGameIndex](#generationgameindex)* |
| names | The name of this item listed in different languages. | list *[Name](#name)* |
| sprites | A set of sprites used to depict this item in the game. | [ItemSprites](#itemsprites) |
| held\_by\_pokemon | A list of Pokémon that might be found in the wild holding this item. | list *[ItemHolderPokemon](#itemholderpokemon)* |
| baby\_trigger\_for | An evolution chain this item requires to produce a bay during mating. | *[APIResource](#apiresource)* (*[EvolutionChain](#evolutionchain)*) |
| machines | A list of the machines related to this item. | list *[MachineVersionDetail](#machineversiondetail)* |

#### ItemSprites (type)

| Name | Description | Type |
| --- | --- | --- |
| default | The default depiction of this item. | *string* |

#### ItemHolderPokemon (type)

| Name | Description | Type |
| --- | --- | --- |
| pokemon | The Pokémon that holds this item. | *[NamedAPIResource](#namedapiresource)* (*[Pokemon](#pokemon)*) |
| version\_details | The details for the version that this item is held in by the Pokémon. | list *[ItemHolderPokemonVersionDetail](#itemholderpokemonversiondetail)* |

#### ItemHolderPokemonVersionDetail (type)

| Name | Description | Type |
| --- | --- | --- |
| rarity | How often this Pokémon holds this item in this version. | *integer* |
| version | The version that this item is held in by the Pokémon. | *[NamedAPIResource](#namedapiresource)* (*[Version](#version)*) |

### Item Attributes (endpoint)

Item attributes define particular aspects of items, e.g. "usable in battle" or "consumable".

GET https://pokeapi.co/api/v2/item-attribute/{id or name}/

- - 1
		- "countable"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Has a count in the bag"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "master-ball"
						- "https://pokeapi.co/api/v2/item/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Countable"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"

#### ItemAttribute (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| items | A list of items that have this attribute. | list **[NamedAPIResource](#namedapiresource)* (*[Item](#item)*)* |
| names | The name of this item attribute listed in different languages. | list *[Name](#name)* |
| descriptions | The description of this item attribute listed in different languages. | list *[Description](#description)* |

### Item Categories (endpoint)

Item categories determine where items will be placed in the players bag.

GET https://pokeapi.co/api/v2/item-category/{id or name}/

- - 1
		- "stat-boosts"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "guard-spec"
						- "https://pokeapi.co/api/v2/item/55/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Stat boosts"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		{} 2 keys
		- "battle"
				- "https://pokeapi.co/api/v2/item-pocket/7/"

#### ItemCategory (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| items | A list of items that are a part of this category. | list **[NamedAPIResource](#namedapiresource)* (*[Item](#item)*)* |
| names | The name of this item category listed in different languages. | list *[Name](#name)* |
| pocket | The pocket items in this category would be put in. | *[NamedAPIResource](#namedapiresource)* (*[ItemPocket](#itempocket)*) |

### Item Fling Effects (endpoint)

The various effects of the move "Fling" when used with different items.

GET https://pokeapi.co/api/v2/item-fling-effect/{id or name}/

- - 1
		- "badly-poison"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Badly poisons the target."
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "toxic-orb"
						- "https://pokeapi.co/api/v2/item/249/"

#### ItemFlingEffect (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| effect\_entries | The result of this fling effect listed in different languages. | list *[Effect](#effect)* |
| items | A list of items that have this fling effect. | list **[NamedAPIResource](#namedapiresource)* (*[Item](#item)*)* |

### Item Pockets (endpoint)

Pockets within the players bag used for storing items by category.

GET https://pokeapi.co/api/v2/item-pocket/{id or name}/

- - 1
		- "misc"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "collectibles"
						- "https://pokeapi.co/api/v2/item-category/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Items"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"

#### ItemPocket (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| categories | A list of item categories that are relevant to this item pocket. | list **[NamedAPIResource](#namedapiresource)* (*[ItemCategory](#itemcategory)*)* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |

## Locations (group)

### Locations (endpoint)

Locations that can be visited within the games. Locations make up sizable portions of regions, like cities or routes.

GET https://pokeapi.co/api/v2/location/{id or name}/

- - 1
		- "canalave-city"
		- ▶
		{} 2 keys
		- "sinnoh"
				- "https://pokeapi.co/api/v2/region/4/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Canalave City"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- 7
						- ▶
				{} 2 keys
				- "generation-iv"
								- "https://pokeapi.co/api/v2/generation/4/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "canalave-city-area"
						- "https://pokeapi.co/api/v2/location-area/1/"

#### Location (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| region | The region this location can be found in. | *[NamedAPIResource](#namedapiresource)* (*[Region](#region)*) |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| game\_indices | A list of game indices relevent to this location by generation. | list *[GenerationGameIndex](#generationgameindex)* |
| areas | Areas that can be found within this location. | list **[NamedAPIResource](#namedapiresource)* (*[LocationArea](#locationarea)*)* |

### Location Areas (endpoint)

Location areas are sections of areas, such as floors in a building or cave. Each area has its own set of possible Pokémon encounters.

GET https://pokeapi.co/api/v2/location-area/{id or name}/

- - 1
		- "canalave-city-area"
		- 1
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- ▶
				{} 2 keys
				- "old-rod"
								- "https://pokeapi.co/api/v2/encounter-method/2/"
						- ▶
				\[\] 1 item
		- ▶
		{} 2 keys
		- "canalave-city"
				- "https://pokeapi.co/api/v2/location/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- ""
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- ▶
				{} 2 keys
				- "tentacool"
								- "https://pokeapi.co/api/v2/pokemon/72/"
						- ▶
				\[\] 1 item

#### LocationArea (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| game\_index | The internal id of an API resource within game data. | *integer* |
| encounter\_method\_rates | A list of methods in which Pokémon may be encountered in this area and how likely the method will occur depending on the version of the game. | list *[EncounterMethodRate](#encountermethodrate)* |
| location | The region this location area can be found in. | *[NamedAPIResource](#namedapiresource)* (*[Location](#location)*) |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| pokemon\_encounters | A list of Pokémon that can be encountered in this area along with version specific details about the encounter. | list *[PokemonEncounter](#pokemonencounter)* |

#### EncounterMethodRate (type)

| Name | Description | Type |
| --- | --- | --- |
| encounter\_method | The method in which Pokémon may be encountered in an area.. | *[NamedAPIResource](#namedapiresource)* (*[EncounterMethod](#encountermethod)*) |
| version\_details | The chance of the encounter to occur on a version of the game. | list *[EncounterVersionDetails](#encounterversiondetails)* |

#### EncounterVersionDetails (type)

| Name | Description | Type |
| --- | --- | --- |
| rate | The chance of an encounter to occur. | *integer* |
| version | The version of the game in which the encounter can occur with the given chance. | *[NamedAPIResource](#namedapiresource)* (*[Version](#version)*) |

#### PokemonEncounter (type)

| Name | Description | Type |
| --- | --- | --- |
| pokemon | The Pokémon being encountered. | *[NamedAPIResource](#namedapiresource)* (*[Pokemon](#pokemon)*) |
| version\_details | A list of versions and encounters with Pokémon that might happen in the referenced location area. | list *[VersionEncounterDetail](#versionencounterdetail)* |

### Pal Park Areas (endpoint)

Areas used for grouping Pokémon encounters in Pal Park. They're like habitats that are specific to [Pal Park](https://bulbapedia.bulbagarden.net/wiki/Pal_Park).

GET https://pokeapi.co/api/v2/pal-park-area/{id or name}/

- - 1
		- "forest"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Forest"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 3 keys
			- 30
						- 50
						- ▶
				{} 2 keys
				- "caterpie"
								- "https://pokeapi.co/api/v2/pokemon-species/10/"

#### PalParkArea (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| pokemon\_encounters | A list of Pokémon encountered in thi pal park area along with details. | list *[PalParkEncounterSpecies](#palparkencounterspecies)* |

#### PalParkEncounterSpecies (type)

| Name | Description | Type |
| --- | --- | --- |
| base\_score | The base score given to the player when this Pokémon is caught during a pal park run. | *integer* |
| rate | The base rate for encountering this Pokémon in this pal park area. | *integer* |
| pokemon\_species | The Pokémon species being encountered. | *[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*) |

### Regions (endpoint)

A region is an organized area of the Pokémon world. Most often, the main difference between regions is the species of Pokémon that can be encountered within them.

GET https://pokeapi.co/api/v2/region/{id or name}/

- - 1
		- "kanto"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "celadon-city"
						- "https://pokeapi.co/api/v2/location/67/"
		- ▶
		{} 2 keys
		- "generation-i"
				- "https://pokeapi.co/api/v2/generation/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Kanto"
						- ▶
				{} 2 keys
				- "de"
								- "https://pokeapi.co/api/v2/language/6/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "kanto"
						- "https://pokeapi.co/api/v2/pokedex/2/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "red-blue"
						- "https://pokeapi.co/api/v2/version-group/1/"

#### Region (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| locations | A list of locations that can be found in this region. | list **[NamedAPIResource](#namedapiresource)* (*[Location](#location)*)* |
| name | The name for this resource. | *string* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| main\_generation | The generation this region was introduced in. | *[NamedAPIResource](#namedapiresource)* (*[Generation](#generation)*) |
| pokedexes | A list of pokédexes that catalogue Pokémon in this region. | list **[NamedAPIResource](#namedapiresource)* (*[Pokedex](#pokedex)*)* |
| version\_groups | A list of version groups where this region can be visited. | list **[NamedAPIResource](#namedapiresource)* (*[VersionGroup](#versiongroup)*)* |

## Machines (group)

### Machines (endpoint)

Machines are the representation of items that teach moves to Pokémon. They vary from version to version, so it is not certain that one specific TM or HM corresponds to a single Machine.

GET https://pokeapi.co/api/v2/machine/{id}/

- - 1
		- ▶
		{} 2 keys
		- "tm01"
				- "https://pokeapi.co/api/v2/item/305/"
		- ▶
		{} 2 keys
		- "mega-punch"
				- "https://pokeapi.co/api/v2/move/5/"
		- ▶
		{} 2 keys
		- "red-blue"
				- "https://pokeapi.co/api/v2/version/1/"

#### Machine (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| item | The TM or HM item that corresponds to this machine. | *[NamedAPIResource](#namedapiresource)* (*[Item](#item)*) |
| move | The move that is taught by this machine. | *[NamedAPIResource](#namedapiresource)* (*[Move](#move)*) |
| version\_group | The version group that this machine applies to. | *[NamedAPIResource](#namedapiresource)* (*[VersionGroup](#versiongroup)*) |

## Moves (group)

### Moves (endpoint)

Moves are the skills of Pokémon in battle. In battle, a Pokémon uses one move each turn. Some moves (including those learned by Hidden Machine) can be used outside of battle as well, usually for the purpose of removing obstacles or exploring new areas.

GET https://pokeapi.co/api/v2/move/{id or name}/

- - 1
		- "pound"
		- 100
		- null
		- 35
		- 0
		- 40
		- ▶
		{} 2 keys
		- ▶
			{} 2 keys
			- ▶
				\[\] 3 items
				- ▶
					{} 2 keys
					- "double-slap"
										- "https://pokeapi.co/api/v2/move/3/"
								- ▶
					{} 2 keys
					- "headbutt"
										- "https://pokeapi.co/api/v2/move/29/"
								- ▶
					{} 2 keys
					- "feint-attack"
										- "https://pokeapi.co/api/v2/move/185/"
						- null
				- ▶
			{} 2 keys
			- null
						- null
		- ▶
		{} 2 keys
		- "tough"
				- "https://pokeapi.co/api/v2/contest-type/5/"
		- ▶
		{} 1 key
		- "https://pokeapi.co/api/v2/contest-effect/1/"
		- ▶
		{} 2 keys
		- "physical"
				- "https://pokeapi.co/api/v2/move-damage-class/2/"
		- ▶
		\[\] 1 item
		- ▶
			{} 3 keys
			- "Inflicts \[regular damage\]{mechanic:regular-damage}."
						- "Inflicts regular damage with no additional effect."
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- \[\] 0 items
		- ▶
		{} 2 keys
		- "generation-i"
				- "https://pokeapi.co/api/v2/generation/1/"
		- ▶
		{} 12 keys
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Pound"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- \[\] 0 items
		- \[\] 0 items
		- ▶
		{} 1 key
		- "https://pokeapi.co/api/v2/super-contest-effect/5/"
		- ▶
		{} 2 keys
		- "selected-pokemon"
				- "https://pokeapi.co/api/v2/move-target/10/"
		- ▶
		{} 2 keys
		- "normal"
				- "https://pokeapi.co/api/v2/type/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "clefairy"
						- "https://pokeapi.co/api/v2/pokemon/35/"
		- ▶
		\[\] 1 item
		- ▶
			{} 3 keys
			- "Pounds with fore­ legs or tail."
						- ▶
				{} 2 keys
				- "https://pokeapi.co/api/v2/language/9/"
								- "en"
						- ▶
				{} 2 keys
				- "https://pokeapi.co/api/v2/version-group/3/"
								- "gold-silver"

#### Move (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| accuracy | The percent value of how likely this move is to be successful. | *integer* |
| effect\_chance | The percent value of how likely it is this moves effect will happen. | *integer* |
| pp | Power points. The number of times this move can be used. | *integer* |
| priority | A value between -8 and 8. Sets the order in which moves are executed during battle. See [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Priority) for greater detail. | *integer* |
| power | The base power of this move with a value of 0 if it does not have a base power. | *integer* |
| contest\_combos | A detail of normal and super contest combos that require this move. | [ContestComboSets](#contestcombosets) |
| contest\_type | The type of appeal this move gives a Pokémon when used in a contest. | *[NamedAPIResource](#namedapiresource)* (*[ContestType](#contesttype)*) |
| contest\_effect | The effect the move has when used in a contest. | *[APIResource](#apiresource)* (*[ContestEffect](#contesteffect)*) |
| damage\_class | The type of damage the move inflicts on the target, e.g. physical. | *[NamedAPIResource](#namedapiresource)* (*[MoveDamageClass](#movedamageclass)*) |
| effect\_entries | The effect of this move listed in different languages. | list *[VerboseEffect](#verboseeffect)* |
| effect\_changes | The list of previous effects this move has had across version groups of the games. | list *[AbilityEffectChange](#abilityeffectchange)* |
| learned\_by\_pokemon | List of Pokemon that can learn the move | list **[NamedAPIResource](#namedapiresource)* (*[Pokemon](#pokemon)*)* |
| flavor\_text\_entries | The flavor text of this move listed in different languages. | list *[MoveFlavorText](#moveflavortext)* |
| generation | The generation in which this move was introduced. | *[NamedAPIResource](#namedapiresource)* (*[Generation](#generation)*) |
| machines | A list of the machines that teach this move. | list *[MachineVersionDetail](#machineversiondetail)* |
| meta | Metadata about this move | [MoveMetaData](#movemetadata) |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| past\_values | A list of move resource value changes across version groups of the game. | list *[PastMoveStatValues](#pastmovestatvalues)* |
| stat\_changes | A list of stats this moves effects and how much it effects them. | list *[MoveStatChange](#movestatchange)* |
| super\_contest\_effect | The effect the move has when used in a super contest. | *[APIResource](#apiresource)* (*[SuperContestEffect](#supercontesteffect)*) |
| target | The type of target that will receive the effects of the attack. | *[NamedAPIResource](#namedapiresource)* (*[MoveTarget](#movetarget)*) |
| type | The elemental type of this move. | *[NamedAPIResource](#namedapiresource)* (*[Type](#type)*) |

#### ContestComboSets (type)

| Name | Description | Type |
| --- | --- | --- |
| normal | A detail of moves this move can be used before or after, granting additional appeal points in contests. | [ContestComboDetail](#contestcombodetail) |
| super | A detail of moves this move can be used before or after, granting additional appeal points in super contests. | [ContestComboDetail](#contestcombodetail) |

#### ContestComboDetail (type)

| Name | Description | Type |
| --- | --- | --- |
| use\_before | A list of moves to use before this move. | list **[NamedAPIResource](#namedapiresource)* (*[Move](#move)*)* |
| use\_after | A list of moves to use after this move. | list **[NamedAPIResource](#namedapiresource)* (*[Move](#move)*)* |

#### MoveFlavorText (type)

| Name | Description | Type |
| --- | --- | --- |
| flavor\_text | The localized flavor text for an api resource in a specific language. | *string* |
| language | The language this name is in. | *[NamedAPIResource](#namedapiresource)* (*[Language](#language)*) |
| version\_group | The version group that uses this flavor text. | *[NamedAPIResource](#namedapiresource)* (*[VersionGroup](#versiongroup)*) |

#### MoveMetaData (type)

| Name | Description | Type |
| --- | --- | --- |
| ailment | The status ailment this move inflicts on its target. | *[NamedAPIResource](#namedapiresource)* (*[MoveAilment](#moveailment)*) |
| category | The category of move this move falls under, e.g. damage or ailment. | *[NamedAPIResource](#namedapiresource)* (*[MoveCategory](#movecategory)*) |
| min\_hits | The minimum number of times this move hits. Null if it always only hits once. | *integer* |
| max\_hits | The maximum number of times this move hits. Null if it always only hits once. | *integer* |
| min\_turns | The minimum number of turns this move continues to take effect. Null if it always only lasts one turn. | *integer* |
| max\_turns | The maximum number of turns this move continues to take effect. Null if it always only lasts one turn. | *integer* |
| drain | HP drain (if positive) or Recoil damage (if negative), in percent of damage done. | *integer* |
| healing | The amount of hp gained by the attacking Pokemon, in percent of it's maximum HP. | *integer* |
| crit\_rate | Critical hit rate bonus. | *integer* |
| ailment\_chance | The likelihood this attack will cause an ailment. | *integer* |
| flinch\_chance | The likelihood this attack will cause the target Pokémon to flinch. | *integer* |
| stat\_chance | The likelihood this attack will cause a stat change in the target Pokémon. | *integer* |

#### MoveStatChange (type)

| Name | Description | Type |
| --- | --- | --- |
| change | The amount of change. | *integer* |
| stat | The stat being affected. | *[NamedAPIResource](#namedapiresource)* (*[Stat](#stat)*) |

#### PastMoveStatValues (type)

| Name | Description | Type |
| --- | --- | --- |
| accuracy | The percent value of how likely this move is to be successful. | *integer* |
| effect\_chance | The percent value of how likely it is this moves effect will take effect. | *integer* |
| power | The base power of this move with a value of 0 if it does not have a base power. | *integer* |
| pp | Power points. The number of times this move can be used. | *integer* |
| effect\_entries | The effect of this move listed in different languages. | list *[VerboseEffect](#verboseeffect)* |
| type | The elemental type of this move. | *[NamedAPIResource](#namedapiresource)* (*[Type](#type)*) |
| version\_group | The version group in which these move stat values were in effect. | *[NamedAPIResource](#namedapiresource)* (*[VersionGroup](#versiongroup)*) |

### Move Ailments (endpoint)

Move Ailments are status conditions caused by moves used during battle. See [Bulbapedia](https://bulbapedia.bulbagarden.net/wiki/Status_condition) for greater detail.

GET https://pokeapi.co/api/v2/move-ailment/{id or name}/

- - 1
		- "paralysis"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "thunder-punch"
						- "https://pokeapi.co/api/v2/move/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Paralysis"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"

#### MoveAilment (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| moves | A list of moves that cause this ailment. | list **[NamedAPIResource](#namedapiresource)* (*[Move](#move)*)* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |

### Move Battle Styles (endpoint)

Styles of moves when used in the Battle Palace. See [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Battle_Frontier_\(Generation_III\)) for greater detail.

GET https://pokeapi.co/api/v2/move-battle-style/{id or name}/

- - 1
		- "attack"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Attack"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"

#### MoveBattleStyle (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |

### Move Categories (endpoint)

Very general categories that loosely group move effects.

GET https://pokeapi.co/api/v2/move-category/{id or name}/

- - 1
		- "ailment"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "No damage; inflicts status ailment"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "sing"
						- "https://pokeapi.co/api/v2/move/47/"

#### MoveCategory (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| moves | A list of moves that fall into this category. | list **[NamedAPIResource](#namedapiresource)* (*[Move](#move)*)* |
| descriptions | The description of this resource listed in different languages. | list *[Description](#description)* |

### Move Damage Classes (endpoint)

Damage classes moves can have, e.g. physical, special, or non-damaging.

GET https://pokeapi.co/api/v2/move-damage-class/{id or name}/

- - 1
		- "status"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "ãƒ€ãƒ¡ãƒ¼ã‚¸ãªã„"
						- ▶
				{} 2 keys
				- "ja"
								- "https://pokeapi.co/api/v2/language/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "swords-dance"
						- "https://pokeapi.co/api/v2/move/14/"

#### MoveDamageClass (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| descriptions | The description of this resource listed in different languages. | list *[Description](#description)* |
| moves | A list of moves that fall into this damage class. | list **[NamedAPIResource](#namedapiresource)* (*[Move](#move)*)* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |

### Move Learn Methods (endpoint)

Methods by which Pokémon can learn moves.

GET https://pokeapi.co/api/v2/move-learn-method/{id or name}/

- - 1
		- "level-up"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Level up"
						- ▶
				{} 2 keys
				- "de"
								- "https://pokeapi.co/api/v2/language/6/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Wird gelernt, wenn ein Pokémon ein bestimmtes Level erreicht."
						- ▶
				{} 2 keys
				- "de"
								- "https://pokeapi.co/api/v2/language/6/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "red-blue"
						- "https://pokeapi.co/api/v2/version-group/1/"

#### MoveLearnMethod (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| descriptions | The description of this resource listed in different languages. | list *[Description](#description)* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| version\_groups | A list of version groups where moves can be learned through this method. | list **[NamedAPIResource](#namedapiresource)* (*[VersionGroup](#versiongroup)*)* |

### Move Targets (endpoint)

Targets moves can be directed at during battle. Targets can be Pokémon, environments or even other moves.

GET https://pokeapi.co/api/v2/move-target/{id or name}/

- - 1
		- "specific-move"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Eine spezifische Fähigkeit. Wie diese Fähigkeit genutzt wird, hängt von den genutzten Fähigkeiten ab."
						- ▶
				{} 2 keys
				- "de"
								- "https://pokeapi.co/api/v2/language/6/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "counter"
						- "https://pokeapi.co/api/v2/move/68/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Spezifische Fähigkeit"
						- ▶
				{} 2 keys
				- "de"
								- "https://pokeapi.co/api/v2/language/6/"

#### MoveTarget (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| descriptions | The description of this resource listed in different languages. | list *[Description](#description)* |
| moves | A list of moves that that are directed at this target. | list **[NamedAPIResource](#namedapiresource)* (*[Move](#move)*)* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |

## Pokémon (group)

### Abilities (endpoint)

Abilities provide passive effects for Pokémon in battle or in the overworld. Pokémon have multiple possible abilities but can have only one ability at a time. Check out [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Ability) for greater detail.

GET https://pokeapi.co/api/v2/ability/{id or name}/

- - 1
		- "stench"
		- true
		- ▶
		{} 2 keys
		- "generation-iii"
				- "https://pokeapi.co/api/v2/generation/3/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Stench"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 3 keys
			- "This Pokémon's damaging moves have a 10% chance to make the target \[flinch\]{mechanic:flinch} with each hit if they do not already cause flinching as a secondary effect. This ability does not stack with a held item. Overworld: The wild encounter rate is halved while this Pokémon is first in the party."
						- "Has a 10% chance of making target Pokémon \[flinch\]{mechanic:flinch} with each hit."
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- ▶
				{} 2 keys
				- "black-white"
								- "https://pokeapi.co/api/v2/version-group/11/"
						- ▶
				\[\] 1 item
		- ▶
		\[\] 1 item
		- ▶
			{} 3 keys
			- "è‡­ãã¦ã€€ç›¸æ‰‹ãŒ ã²ã‚‹ã‚€ã€€ã“ã¨ãŒã‚ã‚‹ã€‚"
						- ▶
				{} 2 keys
				- "ja-kanji"
								- "https://pokeapi.co/api/v2/language/11/"
						- ▶
				{} 2 keys
				- "x-y"
								- "https://pokeapi.co/api/v2/version-group/15/"
		- ▶
		\[\] 1 item
		- ▶
			{} 3 keys
			- true
						- 3
						- ▶
				{} 2 keys
				- "gloom"
								- "https://pokeapi.co/api/v2/pokemon/44/"

#### Ability (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| is\_main\_series | Whether or not this ability originated in the main series of the video games. | *boolean* |
| generation | The generation this ability originated in. | *[NamedAPIResource](#namedapiresource)* (*[Generation](#generation)*) |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| effect\_entries | The effect of this ability listed in different languages. | list *[VerboseEffect](#verboseeffect)* |
| effect\_changes | The list of previous effects this ability has had across version groups. | list *[AbilityEffectChange](#abilityeffectchange)* |
| flavor\_text\_entries | The flavor text of this ability listed in different languages. | list *[AbilityFlavorText](#abilityflavortext)* |
| pokemon | A list of Pokémon that could potentially have this ability. | list *[AbilityPokemon](#abilitypokemon)* |

#### AbilityEffectChange (type)

| Name | Description | Type |
| --- | --- | --- |
| effect\_entries | The previous effect of this ability listed in different languages. | list *[Effect](#effect)* |
| version\_group | The version group in which the previous effect of this ability originated. | *[NamedAPIResource](#namedapiresource)* (*[VersionGroup](#versiongroup)*) |

#### AbilityFlavorText (type)

| Name | Description | Type |
| --- | --- | --- |
| flavor\_text | The localized name for an API resource in a specific language. | *string* |
| language | The language this text resource is in. | *[NamedAPIResource](#namedapiresource)* (*[Language](#language)*) |
| version\_group | The version group that uses this flavor text. | *[NamedAPIResource](#namedapiresource)* (*[VersionGroup](#versiongroup)*) |

#### AbilityPokemon (type)

| Name | Description | Type |
| --- | --- | --- |
| is\_hidden | Whether or not this a hidden ability for the referenced Pokémon. | *boolean* |
| slot | Pokémon have 3 ability 'slots' which hold references to possible abilities they could have. This is the slot of this ability for the referenced pokemon. | *integer* |
| pokemon | The Pokémon this ability could belong to. | *[NamedAPIResource](#namedapiresource)* (*[Pokemon](#pokemon)*) |

### Characteristics (endpoint)

Characteristics indicate which stat contains a Pokémon's highest IV. A Pokémon's Characteristic is determined by the remainder of its highest IV divided by 5 (gene\_modulo). Check out [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Characteristic) for greater detail.

GET https://pokeapi.co/api/v2/characteristic/{id}/

- - 1
		- 0
		- ▶
		\[\] 7 items
		- ▶
		{} 2 keys
		- "hp"
				- "https://pokeapi.co/api/v2/stat/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Loves to eat"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"

#### Characteristic (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| gene\_modulo | The remainder of the highest stat/IV divided by 5. | *integer* |
| possible\_values | The possible values of the highest stat that would result in a Pokémon recieving this characteristic when divided by 5. | list **integer** |
| highest\_stat | The stat which results in this characteristic. | *[NamedAPIResource](#namedapiresource)* (*[Stat](#stat)*) |
| descriptions | The descriptions of this characteristic listed in different languages. | list *[Description](#description)* |

### Egg Groups (endpoint)

Egg Groups are categories which determine which Pokémon are able to interbreed. Pokémon may belong to either one or two Egg Groups. Check out [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Egg_Group) for greater detail.

GET https://pokeapi.co/api/v2/egg-group/{id or name}/

- - 1
		- "monster"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "かいじゅう"
						- ▶
				{} 2 keys
				- "ja"
								- "https://pokeapi.co/api/v2/language/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "bulbasaur"
						- "https://pokeapi.co/api/v2/pokemon-species/1/"

#### EggGroup (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| pokemon\_species | A list of all Pokémon species that are members of this egg group. | list **[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*)* |

### Genders (endpoint)

Genders were introduced in Generation II for the purposes of breeding Pokémon but can also result in visual differences or even different evolutionary lines. Check out [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Gender) for greater detail.

GET https://pokeapi.co/api/v2/gender/{id or name}/

- - 1
		- "female"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- 1
						- ▶
				{} 2 keys
				- "bulbasaur"
								- "https://pokeapi.co/api/v2/pokemon-species/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "wormadam"
						- "https://pokeapi.co/api/v2/pokemon-species/413/"

#### Gender (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| pokemon\_species\_details | A list of Pokémon species that can be this gender and how likely it is that they will be. | list *[PokemonSpeciesGender](#pokemonspeciesgender)* |
| required\_for\_evolution | A list of Pokémon species that required this gender in order for a Pokémon to evolve into them. | list **[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*)* |

#### PokemonSpeciesGender (type)

| Name | Description | Type |
| --- | --- | --- |
| rate | The chance of this Pokémon being female, in eighths; or -1 for genderless. | *integer* |
| pokemon\_species | A Pokémon species that can be the referenced gender. | *[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*) |

### Growth Rates (endpoint)

Growth rates are the speed with which Pokémon gain levels through experience. Check out [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Experience) for greater detail.

GET https://pokeapi.co/api/v2/growth-rate/{id or name}/

- - 1
		- "slow"
		- "\\frac{5x^3}{4}"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "langsam"
						- ▶
				{} 2 keys
				- "de"
								- "https://pokeapi.co/api/v2/language/6/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- 100
						- 1250000
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "growlithe"
						- "https://pokeapi.co/api/v2/pokemon-species/58/"

#### GrowthRate (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| formula | The formula used to calculate the rate at which the Pokémon species gains level. | *string* |
| descriptions | The descriptions of this characteristic listed in different languages. | list *[Description](#description)* |
| levels | A list of levels and the amount of experienced needed to atain them based on this growth rate. | list *[GrowthRateExperienceLevel](#growthrateexperiencelevel)* |
| pokemon\_species | A list of Pokémon species that gain levels at this growth rate. | list **[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*)* |

#### GrowthRateExperienceLevel (type)

| Name | Description | Type |
| --- | --- | --- |
| level | The level gained. | *integer* |
| experience | The amount of experience required to reach the referenced level. | *integer* |

### Natures (endpoint)

Natures influence how a Pokémon's stats grow. See [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Nature) for greater detail.

GET https://pokeapi.co/api/v2/nature/{id or name}/

- - 2
		- "bold"
		- ▶
		{} 2 keys
		- "attack"
				- "https://pokeapi.co/api/v2/stat/2/"
		- ▶
		{} 2 keys
		- "defense"
				- "https://pokeapi.co/api/v2/stat/3/"
		- ▶
		{} 2 keys
		- "sour"
				- "https://pokeapi.co/api/v2/berry-flavor/5/"
		- ▶
		{} 2 keys
		- "spicy"
				- "https://pokeapi.co/api/v2/berry-flavor/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- \-2
						- ▶
				{} 2 keys
				- "speed"
								- "https://pokeapi.co/api/v2/pokeathlon-stat/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 3 keys
			- 32
						- 30
						- ▶
				{} 2 keys
				- "attack"
								- "https://pokeapi.co/api/v2/move-battle-style/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "がんばりや"
						- ▶
				{} 2 keys
				- "ja"
								- "https://pokeapi.co/api/v2/language/1/"

#### Nature (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| decreased\_stat | The stat decreased by 10% in Pokémon with this nature. | *[NamedAPIResource](#namedapiresource)* (*[Stat](#stat)*) |
| increased\_stat | The stat increased by 10% in Pokémon with this nature. | *[NamedAPIResource](#namedapiresource)* (*[Stat](#stat)*) |
| hates\_flavor | The flavor hated by Pokémon with this nature. | *[NamedAPIResource](#namedapiresource)* (*[BerryFlavor](#berryflavor)*) |
| likes\_flavor | The flavor liked by Pokémon with this nature. | *[NamedAPIResource](#namedapiresource)* (*[BerryFlavor](#berryflavor)*) |
| pokeathlon\_stat\_changes | A list of Pokéathlon stats this nature effects and how much it effects them. | list *[NatureStatChange](#naturestatchange)* |
| move\_battle\_style\_preferences | A list of battle styles and how likely a Pokémon with this nature is to use them in the Battle Palace or Battle Tent. | list *[MoveBattleStylePreference](#movebattlestylepreference)* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |

#### NatureStatChange (type)

| Name | Description | Type |
| --- | --- | --- |
| max\_change | The amount of change. | *integer* |
| pokeathlon\_stat | The stat being affected. | *[NamedAPIResource](#namedapiresource)* (*[PokeathlonStat](#pokeathlonstat)*) |

#### MoveBattleStylePreference (type)

| Name | Description | Type |
| --- | --- | --- |
| low\_hp\_preference | Chance of using the move, in percent, if HP is under one half. | *integer* |
| high\_hp\_preference | Chance of using the move, in percent, if HP is over one half. | *integer* |
| move\_battle\_style | The move battle style. | *[NamedAPIResource](#namedapiresource)* (*[MoveBattleStyle](#movebattlestyle)*) |

### Pokeathlon Stats (endpoint)

Pokeathlon Stats are different attributes of a Pokémon's performance in Pokéathlons. In Pokéathlons, competitions happen on different courses; one for each of the different Pokéathlon stats. See [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Pok%C3%A9athlon) for greater detail.

GET https://pokeapi.co/api/v2/pokeathlon-stat/{id or name}/

- - 1
		- "speed"
		- ▶
		{} 2 keys
		- ▶
			\[\] 1 item
			- ▶
				{} 2 keys
				- 2
								- ▶
					{} 2 keys
					- "timid"
										- "https://pokeapi.co/api/v2/nature/5/"
				- ▶
			\[\] 1 item
			- ▶
				{} 2 keys
				- \-1
								- ▶
					{} 2 keys
					- "hardy"
										- "https://pokeapi.co/api/v2/nature/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Speed"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"

#### PokeathlonStat (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| affecting\_natures | A detail of natures which affect this Pokéathlon stat positively or negatively. | [NaturePokeathlonStatAffectSets](#naturepokeathlonstataffectsets) |

#### NaturePokeathlonStatAffectSets (type)

| Name | Description | Type |
| --- | --- | --- |
| increase | A list of natures and how they change the referenced Pokéathlon stat. | list *[NaturePokeathlonStatAffect](#naturepokeathlonstataffect)* |
| decrease | A list of natures and how they change the referenced Pokéathlon stat. | list *[NaturePokeathlonStatAffect](#naturepokeathlonstataffect)* |

#### NaturePokeathlonStatAffect (type)

| Name | Description | Type |
| --- | --- | --- |
| max\_change | The maximum amount of change to the referenced Pokéathlon stat. | *integer* |
| nature | The nature causing the change. | *[NamedAPIResource](#namedapiresource)* (*[Nature](#nature)*) |

### Pokemon (endpoint)

Pokémon are the creatures that inhabit the world of the Pokémon games. They can be caught using Pokéballs and trained by battling with other Pokémon. Each Pokémon belongs to a specific species but may take on a variant which makes it differ from other Pokémon of the same species, such as base stats, available abilities and typings. See [Bulbapedia](http://bulbapedia.bulbagarden.net/wiki/Pok%C3%A9mon_\(species\)) for greater detail.

GET https://pokeapi.co/api/v2/pokemon/{id or name}/

- - 35
		- "clefairy"
		- 113
		- 6
		- true
		- 56
		- 75
		- ▶
		\[\] 1 item
		- ▶
			{} 3 keys
			- true
						- 3
						- ▶
				{} 2 keys
				- "friend-guard"
								- "https://pokeapi.co/api/v2/ability/132/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "clefairy"
						- "https://pokeapi.co/api/v2/pokemon-form/35/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- 35
						- ▶
				{} 2 keys
				- "white-2"
								- "https://pokeapi.co/api/v2/version/22/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- ▶
				{} 2 keys
				- "moon-stone"
								- "https://pokeapi.co/api/v2/item/81/"
						- ▶
				\[\] 1 item
		- "/api/v2/pokemon/35/encounters"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- ▶
				{} 2 keys
				- "pound"
								- "https://pokeapi.co/api/v2/move/1/"
						- ▶
				\[\] 1 item
		- ▶
		{} 2 keys
		- "clefairy"
				- "https://pokeapi.co/api/v2/pokemon-species/35/"
		- ▶
		{} 10 keys
		- ▶
		{} 2 keys
		- "https://raw.githubusercontent.com/PokeAPI/cries/main/cries/pokemon/latest/35.ogg"
				- "https://raw.githubusercontent.com/PokeAPI/cries/main/cries/pokemon/legacy/35.ogg"
		- ▶
		\[\] 1 item
		- ▶
			{} 3 keys
			- 35
						- 0
						- ▶
				{} 2 keys
				- "speed"
								- "https://pokeapi.co/api/v2/stat/6/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- 1
						- ▶
				{} 2 keys
				- "fairy"
								- "https://pokeapi.co/api/v2/type/18/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- ▶
				{} 2 keys
				- "generation-v"
								- "https://pokeapi.co/api/v2/generation/5/"
						- ▶
				\[\] 1 item
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- ▶
				{} 2 keys
				- "generation-iv"
								- "https://pokeapi.co/api/v2/generation/4/"
						- ▶
				\[\] 1 item

#### Pokemon (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| base\_experience | The base experience gained for defeating this Pokémon. | *integer* |
| height | The height of this Pokémon in decimetres. | *integer* |
| is\_default | Set for exactly one Pokémon used as the default for each species. | *boolean* |
| order | Order for sorting. Almost national order, except families are grouped together. | *integer* |
| weight | The weight of this Pokémon in hectograms. | *integer* |
| abilities | A list of abilities this Pokémon could potentially have. | list *[PokemonAbility](#pokemonability)* |
| forms | A list of forms this Pokémon can take on. | list **[NamedAPIResource](#namedapiresource)* (*[PokemonForm](#pokemonform)*)* |
| game\_indices | A list of game indices relevent to Pokémon item by generation. | list *[VersionGameIndex](#versiongameindex)* |
| held\_items | A list of items this Pokémon may be holding when encountered. | list *[PokemonHeldItem](#pokemonhelditem)* |
| location\_area\_encounters | A link to a list of location areas, as well as encounter details pertaining to specific versions. | *string* |
| moves | A list of moves along with learn methods and level details pertaining to specific version groups. | list *[PokemonMove](#pokemonmove)* |
| past\_types | A list of details showing types this pokémon had in previous generations | list *[PokemonTypePast](#pokemontypepast)* |
| past\_abilities | A list of details showing abilities this pokémon had in previous generations | list *[PokemonAbilityPast](#pokemonabilitypast)* |
| past\_stats | A list of details showing stats this pokémon had in previous generations | list *[PokemonStatPast](#pokemonstatpast)* |
| sprites | A set of sprites used to depict this Pokémon in the game. A visual representation of the various sprites can be found at [PokeAPI/sprites](https://github.com/PokeAPI/sprites#sprites) | [PokemonSprites](#pokemonsprites) |
| cries | A set of cries used to depict this Pokémon in the game. A visual representation of the various cries can be found at [PokeAPI/cries](https://github.com/PokeAPI/cries#cries) | [PokemonCries](#pokemoncries) |
| species | The species this Pokémon belongs to. | *[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*) |
| stats | A list of base stat values for this Pokémon. | list *[PokemonStat](#pokemonstat)* |
| types | A list of details showing types this Pokémon has. | list *[PokemonType](#pokemontype)* |

#### PokemonAbility (type)

| Name | Description | Type |
| --- | --- | --- |
| is\_hidden | Whether or not this is a hidden ability. | *boolean* |
| slot | The slot this ability occupies in this Pokémon species. | *integer* |
| ability | The ability the Pokémon may have. | *[NamedAPIResource](#namedapiresource)* (*[Ability](#ability)*) |

#### PokemonType (type)

| Name | Description | Type |
| --- | --- | --- |
| slot | The order the Pokémon's types are listed in. | *integer* |
| type | The type the referenced Pokémon has. | *[NamedAPIResource](#namedapiresource)* (*[Type](#type)*) |

#### PokemonFormType (type)

| Name | Description | Type |
| --- | --- | --- |
| slot | The order the Pokémon's types are listed in. | *integer* |
| type | The type the referenced Form has. | *[NamedAPIResource](#namedapiresource)* (*[Type](#type)*) |

#### PokemonTypePast (type)

| Name | Description | Type |
| --- | --- | --- |
| generation | The last generation in which the referenced pokémon had the listed types. | *[NamedAPIResource](#namedapiresource)* (*[Generation](#generation)*) |
| types | The types the referenced pokémon had up to and including the listed generation. | list *[PokemonType](#pokemontype)* |

#### PokemonAbilityPast (type)

| Name | Description | Type |
| --- | --- | --- |
| generation | The last generation in which the referenced pokémon had the listed abilities. | *[NamedAPIResource](#namedapiresource)* (*[Generation](#generation)*) |
| abilities | The abilities the referenced pokémon had up to and including the listed generation. If null, the slot was previously empty. | list *[PokemonAbility](#pokemonability)* |

#### PokemonStatPast (type)

| Name | Description | Type |
| --- | --- | --- |
| generation | The last generation in which the referenced pokémon had the listed stats. | *[NamedAPIResource](#namedapiresource)* (*[Generation](#generation)*) |
| stats | The stat the Pokémon had up to and including the listed generation. | list *[PokemonStat](#pokemonstat)* |

#### PokemonHeldItem (type)

| Name | Description | Type |
| --- | --- | --- |
| item | The item the referenced Pokémon holds. | *[NamedAPIResource](#namedapiresource)* (*[Item](#item)*) |
| version\_details | The details of the different versions in which the item is held. | list *[PokemonHeldItemVersion](#pokemonhelditemversion)* |

#### PokemonHeldItemVersion (type)

| Name | Description | Type |
| --- | --- | --- |
| version | The version in which the item is held. | *[NamedAPIResource](#namedapiresource)* (*[Version](#version)*) |
| rarity | How often the item is held. | *integer* |

#### PokemonMove (type)

| Name | Description | Type |
| --- | --- | --- |
| move | The move the Pokémon can learn. | *[NamedAPIResource](#namedapiresource)* (*[Move](#move)*) |
| version\_group\_details | The details of the version in which the Pokémon can learn the move. | list *[PokemonMoveVersion](#pokemonmoveversion)* |

#### PokemonMoveVersion (type)

| Name | Description | Type |
| --- | --- | --- |
| move\_learn\_method | The method by which the move is learned. | *[NamedAPIResource](#namedapiresource)* (*[MoveLearnMethod](#movelearnmethod)*) |
| version\_group | The version group in which the move is learned. | *[NamedAPIResource](#namedapiresource)* (*[VersionGroup](#versiongroup)*) |
| level\_learned\_at | The minimum level to learn the move. | *integer* |
| order | Order by which the pokemon will learn the move. A newly learnt move will replace the move with lowest order. | *integer* |

#### PokemonStat (type)

| Name | Description | Type |
| --- | --- | --- |
| stat | The stat the Pokémon has. | *[NamedAPIResource](#namedapiresource)* (*[Stat](#stat)*) |
| effort | The effort points (EV) the Pokémon has in the stat. | *integer* |
| base\_stat | The base value of the stat. | *integer* |

#### PokemonSprites (type)

| Name | Description | Type |
| --- | --- | --- |
| front\_default | The default depiction of this Pokémon from the front in battle. | *string* |
| front\_shiny | The shiny depiction of this Pokémon from the front in battle. | *string* |
| front\_female | The female depiction of this Pokémon from the front in battle. | *string* |
| front\_shiny\_female | The shiny female depiction of this Pokémon from the front in battle. | *string* |
| back\_default | The default depiction of this Pokémon from the back in battle. | *string* |
| back\_shiny | The shiny depiction of this Pokémon from the back in battle. | *string* |
| back\_female | The female depiction of this Pokémon from the back in battle. | *string* |
| back\_shiny\_female | The shiny female depiction of this Pokémon from the back in battle. | *string* |

#### PokemonCries (type)

| Name | Description | Type |
| --- | --- | --- |
| latest | The latest depiction of this Pokémon's cry. | *string* |
| legacy | The legacy depiction of this Pokémon's cry. | *string* |

### Pokemon Location Areas (endpoint)

Pokémon Location Areas are ares where Pokémon can be found.

GET https://pokeapi.co/api/v2/pokemon/{id or name}/encounters

- - ▶
		{} 2 keys
		- ▶
			{} 2 keys
			- "kanto-route-2-south-towards-viridian-city"
						- "https://pokeapi.co/api/v2/location-area/296/"
				- ▶
			\[\] 1 item

#### LocationAreaEncounter (type)

| Name | Description | Type |
| --- | --- | --- |
| location\_area | The location area the referenced Pokémon can be encountered in. | *[NamedAPIResource](#namedapiresource)* (*[LocationArea](#locationarea)*) |
| version\_details | A list of versions and encounters with the referenced Pokémon that might happen. | list *[VersionEncounterDetail](#versionencounterdetail)* |

### Pokemon Colors (endpoint)

Colors used for sorting Pokémon in a Pokédex. The color listed in the Pokédex is usually the color most apparent or covering each Pokémon's body. No orange category exists; Pokémon that are primarily orange are listed as red or brown.

GET https://pokeapi.co/api/v2/pokemon-color/{id or name}/

- - 1
		- "black"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "é»’ã„"
						- ▶
				{} 2 keys
				- "ja"
								- "https://pokeapi.co/api/v2/language/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "snorlax"
						- "https://pokeapi.co/api/v2/pokemon-species/143/"

#### PokemonColor (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| pokemon\_species | A list of the Pokémon species that have this color. | list **[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*)* |

### Pokemon Forms (endpoint)

Some Pokémon may appear in one of multiple, visually different forms. These differences are purely cosmetic. For variations within a Pokémon species, which do differ in more than just visuals, the 'Pokémon' entity is used to represent such a variety.

GET https://pokeapi.co/api/v2/pokemon-form/{id or name}/

- - 10041
		- "arceus-bug"
		- 631
		- 7
		- false
		- false
		- false
		- "bug"
		- ▶
		{} 2 keys
		- "arceus"
				- "https://pokeapi.co/api/v2/pokemon/493/"
		- ▶
		{} 8 keys
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- 1
						- ▶
				{} 2 keys
				- "bug"
								- "https://pokeapi.co/api/v2/type/7/"
		- ▶
		{} 2 keys
		- "diamond-pearl"
				- "https://pokeapi.co/api/v2/version-group/8/"

#### PokemonForm (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| order | The order in which forms should be sorted within all forms. Multiple forms may have equal order, in which case they should fall back on sorting by name. | *integer* |
| form\_order | The order in which forms should be sorted within a species' forms. | *integer* |
| is\_default | True for exactly one form used as the default for each Pokémon. | *boolean* |
| is\_battle\_only | Whether or not this form can only happen during battle. | *boolean* |
| is\_mega | Whether or not this form requires mega evolution. | *boolean* |
| form\_name | The name of this form. | *string* |
| pokemon | The Pokémon that can take on this form. | *[NamedAPIResource](#namedapiresource)* (*[Pokemon](#pokemon)*) |
| types | A list of details showing types this Pokémon form has. | list *[PokemonFormType](#pokemonformtype)* |
| sprites | A set of sprites used to depict this Pokémon form in the game. | [PokemonFormSprites](#pokemonformsprites) |
| version\_group | The version group this Pokémon form was introduced in. | *[NamedAPIResource](#namedapiresource)* (*[VersionGroup](#versiongroup)*) |
| names | The form specific full name of this Pokémon form, or empty if the form does not have a specific name. | list *[Name](#name)* |
| form\_names | The form specific form name of this Pokémon form, or empty if the form does not have a specific name. | list *[Name](#name)* |

#### PokemonFormSprites (type)

| Name | Description | Type |
| --- | --- | --- |
| front\_default | The default depiction of this Pokémon form from the front in battle. | *string* |
| front\_shiny | The shiny depiction of this Pokémon form from the front in battle. | *string* |
| back\_default | The default depiction of this Pokémon form from the back in battle. | *string* |
| back\_shiny | The shiny depiction of this Pokémon form from the back in battle. | *string* |

### Pokemon Habitats (endpoint)

Habitats are generally different terrain Pokémon can be found in but can also be areas designated for rare or legendary Pokémon.

GET https://pokeapi.co/api/v2/pokemon-habitat/{id or name}/

- - 1
		- "cave"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "grottes"
						- ▶
				{} 2 keys
				- "fr"
								- "https://pokeapi.co/api/v2/language/5/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "zubat"
						- "https://pokeapi.co/api/v2/pokemon-species/41/"

#### PokemonHabitat (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| pokemon\_species | A list of the Pokémon species that can be found in this habitat. | list **[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*)* |

### Pokemon Shapes (endpoint)

Shapes used for sorting Pokémon in a Pokédex.

GET https://pokeapi.co/api/v2/pokemon-shape/{id or name}/

- - 1
		- "ball"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Pomaceous"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Ball"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "shellder"
						- "https://pokeapi.co/api/v2/pokemon-species/90/"

#### PokemonShape (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| awesome\_names | The "scientific" name of this Pokémon shape listed in different languages. | list *[AwesomeName](#awesomename)* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| pokemon\_species | A list of the Pokémon species that have this shape. | list **[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*)* |

#### AwesomeName (type)

| Name | Description | Type |
| --- | --- | --- |
| awesome\_name | The localized "scientific" name for an API resource in a specific language. | *string* |
| language | The language this "scientific" name is in. | *[NamedAPIResource](#namedapiresource)* (*[Language](#language)*) |

### Pokemon Species (endpoint)

A Pokémon Species forms the basis for at least one Pokémon. Attributes of a Pokémon species are shared across all varieties of Pokémon within the species. A good example is Wormadam; Wormadam is the species which can be found in three different varieties, Wormadam-Trash, Wormadam-Sandy and Wormadam-Plant.

GET https://pokeapi.co/api/v2/pokemon-species/{id or name}/

- - 413
		- "wormadam"
		- 441
		- 8
		- 45
		- 70
		- false
		- false
		- false
		- 15
		- false
		- false
		- ▶
		{} 2 keys
		- "medium"
				- "https://pokeapi.co/api/v2/growth-rate/2/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- 45
						- ▶
				{} 2 keys
				- "kalos-central"
								- "https://pokeapi.co/api/v2/pokedex/12/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "bug"
						- "https://pokeapi.co/api/v2/egg-group/3/"
		- ▶
		{} 2 keys
		- "gray"
				- "https://pokeapi.co/api/v2/pokemon-color/4/"
		- ▶
		{} 2 keys
		- "squiggle"
				- "https://pokeapi.co/api/v2/pokemon-shape/2/"
		- ▶
		{} 2 keys
		- "burmy"
				- "https://pokeapi.co/api/v2/pokemon-species/412/"
		- ▶
		{} 1 key
		- "https://pokeapi.co/api/v2/evolution-chain/213/"
		- null
		- ▶
		{} 2 keys
		- "generation-iv"
				- "https://pokeapi.co/api/v2/generation/4/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Wormadam"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 3 keys
			- "When the bulb on its back grows large, it appearsto lose the ability to stand on its hind legs."
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
						- ▶
				{} 2 keys
				- "red"
								- "https://pokeapi.co/api/v2/version/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Forms have different stats and movepools. During evolution, Burmy's current cloak becomes Wormadam's form, and can no longer be changed."
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Bagworm"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- true
						- ▶
				{} 2 keys
				- "wormadam-plant"
								- "https://pokeapi.co/api/v2/pokemon/413/"

#### PokemonSpecies (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| order | The order in which species should be sorted. Based on National Dex order, except families are grouped together and sorted by stage. | *integer* |
| gender\_rate | The chance of this Pokémon being female, in eighths; or -1 for genderless. | *integer* |
| capture\_rate | The base capture rate; up to 255. The higher the number, the easier the catch. | *integer* |
| base\_happiness | The happiness when caught by a normal Pokéball; up to 255. The higher the number, the happier the Pokémon. | *integer* |
| is\_baby | Whether or not this is a baby Pokémon. | *boolean* |
| is\_legendary | Whether or not this is a legendary Pokémon. | *boolean* |
| is\_mythical | Whether or not this is a mythical Pokémon. | *boolean* |
| hatch\_counter | Initial hatch counter: one must walk Y × (hatch\_counter + 1) steps before this Pokémon's egg hatches, unless utilizing bonuses like Flame Body's. Y varies per generation. In Generations II, III, and VII, Egg cycles are 256 steps long. In Generation IV, Egg cycles are 255 steps long. In Pokémon Brilliant Diamond and Shining Pearl, Egg cycles are also 255 steps long, but are shorter on special dates. In Generations V and VI, Egg cycles are 257 steps long. In Pokémon Sword and Shield, and in Pokémon Scarlet and Violet, Egg cycles are 128 steps long. | *integer* |
| has\_gender\_differences | Whether or not this Pokémon has visual gender differences. | *boolean* |
| forms\_switchable | Whether or not this Pokémon has multiple forms and can switch between them. | *boolean* |
| growth\_rate | The rate at which this Pokémon species gains levels. | *[NamedAPIResource](#namedapiresource)* (*[GrowthRate](#growthrate)*) |
| pokedex\_numbers | A list of Pokedexes and the indexes reserved within them for this Pokémon species. | list *[PokemonSpeciesDexEntry](#pokemonspeciesdexentry)* |
| egg\_groups | A list of egg groups this Pokémon species is a member of. | list **[NamedAPIResource](#namedapiresource)* (*[EggGroup](#egggroup)*)* |
| color | The color of this Pokémon for Pokédex search. | *[NamedAPIResource](#namedapiresource)* (*[PokemonColor](#pokemoncolor)*) |
| shape | The shape of this Pokémon for Pokédex search. | *[NamedAPIResource](#namedapiresource)* (*[PokemonShape](#pokemonshape)*) |
| evolves\_from\_species | The Pokémon species that evolves into this Pokemon\_species. | *[NamedAPIResource](#namedapiresource)* (*[PokemonSpecies](#pokemonspecies)*) |
| evolution\_chain | The evolution chain this Pokémon species is a member of. | *[APIResource](#apiresource)* (*[EvolutionChain](#evolutionchain)*) |
| habitat | The habitat this Pokémon species can be encountered in. | *[NamedAPIResource](#namedapiresource)* (*[PokemonHabitat](#pokemonhabitat)*) |
| generation | The generation this Pokémon species was introduced in. | *[NamedAPIResource](#namedapiresource)* (*[Generation](#generation)*) |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| pal\_park\_encounters | A list of encounters that can be had with this Pokémon species in pal park. | list *[PalParkEncounterArea](#palparkencounterarea)* |
| flavor\_text\_entries | A list of flavor text entries for this Pokémon species. | list *[FlavorText](#flavortext)* |
| form\_descriptions | Descriptions of different forms Pokémon take on within the Pokémon species. | list *[Description](#description)* |
| genera | The genus of this Pokémon species listed in multiple languages. | list *[Genus](#genus)* |
| varieties | A list of the Pokémon that exist within this Pokémon species. | list *[PokemonSpeciesVariety](#pokemonspeciesvariety)* |

#### Genus (type)

| Name | Description | Type |
| --- | --- | --- |
| genus | The localized genus for the referenced Pokémon species | *string* |
| language | The language this genus is in. | *[NamedAPIResource](#namedapiresource)* (*[Language](#language)*) |

#### PokemonSpeciesDexEntry (type)

| Name | Description | Type |
| --- | --- | --- |
| entry\_number | The index number within the Pokédex. | *integer* |
| pokedex | The Pokédex the referenced Pokémon species can be found in. | *[NamedAPIResource](#namedapiresource)* (*[Pokedex](#pokedex)*) |

#### PalParkEncounterArea (type)

| Name | Description | Type |
| --- | --- | --- |
| base\_score | The base score given to the player when the referenced Pokémon is caught during a pal park run. | *integer* |
| rate | The base rate for encountering the referenced Pokémon in this pal park area. | *integer* |
| area | The pal park area where this encounter happens. | *[NamedAPIResource](#namedapiresource)* (*[PalParkArea](#palparkarea)*) |

#### PokemonSpeciesVariety (type)

| Name | Description | Type |
| --- | --- | --- |
| is\_default | Whether this variety is the default variety. | *boolean* |
| pokemon | The Pokémon variety. | *[NamedAPIResource](#namedapiresource)* (*[Pokemon](#pokemon)*) |

### Stats (endpoint)

Stats determine certain aspects of battles. Each Pokémon has a value for each stat which grows as they gain levels and can be altered momentarily by effects in battles.

GET https://pokeapi.co/api/v2/stat/{id or name}/

- - 2
		- "attack"
		- 2
		- false
		- ▶
		{} 2 keys
		- ▶
			\[\] 1 item
			- ▶
				{} 2 keys
				- 2
								- ▶
					{} 2 keys
					- "swords-dance"
										- "https://pokeapi.co/api/v2/move/14/"
				- ▶
			\[\] 1 item
			- ▶
				{} 2 keys
				- \-1
								- ▶
					{} 2 keys
					- "growl"
										- "https://pokeapi.co/api/v2/move/45/"
		- ▶
		{} 2 keys
		- ▶
			\[\] 1 item
			- ▶
				{} 2 keys
				- "lonely"
								- "https://pokeapi.co/api/v2/nature/6/"
				- ▶
			\[\] 1 item
			- ▶
				{} 2 keys
				- "bold"
								- "https://pokeapi.co/api/v2/nature/2/"
		- ▶
		\[\] 1 item
		- ▶
			{} 1 key
			- "https://pokeapi.co/api/v2/characteristic/2/"
		- ▶
		{} 2 keys
		- "physical"
				- "https://pokeapi.co/api/v2/move-damage-class/2/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "ã“ã†ã’ã"
						- ▶
				{} 2 keys
				- "ja"
								- "https://pokeapi.co/api/v2/language/1/"

#### Stat (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| game\_index | ID the games use for this stat. | *integer* |
| is\_battle\_only | Whether this stat only exists within a battle. | *boolean* |
| affecting\_moves | A detail of moves which affect this stat positively or negatively. | [MoveStatAffectSets](#movestataffectsets) |
| affecting\_natures | A detail of natures which affect this stat positively or negatively. | [NatureStatAffectSets](#naturestataffectsets) |
| characteristics | A list of characteristics that are set on a Pokémon when its highest base stat is this stat. | list **[APIResource](#apiresource)* (*[Characteristic](#characteristic)*)* |
| move\_damage\_class | The class of damage this stat is directly related to. | *[NamedAPIResource](#namedapiresource)* (*[MoveDamageClass](#movedamageclass)*) |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |

#### MoveStatAffectSets (type)

| Name | Description | Type |
| --- | --- | --- |
| increase | A list of moves and how they change the referenced stat. | list *[MoveStatAffect](#movestataffect)* |
| decrease | A list of moves and how they change the referenced stat. | list *[MoveStatAffect](#movestataffect)* |

#### MoveStatAffect (type)

| Name | Description | Type |
| --- | --- | --- |
| change | The maximum amount of change to the referenced stat. | *integer* |
| move | The move causing the change. | *[NamedAPIResource](#namedapiresource)* (*[Move](#move)*) |

#### NatureStatAffectSets (type)

| Name | Description | Type |
| --- | --- | --- |
| increase | A list of natures and how they change the referenced stat. | list **[NamedAPIResource](#namedapiresource)* (*[Nature](#nature)*)* |
| decrease | A list of nature sand how they change the referenced stat. | list **[NamedAPIResource](#namedapiresource)* (*[Nature](#nature)*)* |

### Types (endpoint)

Types are properties for Pokémon and their moves. Each type has three properties: which types of Pokémon it is super effective against, which types of Pokémon it is not very effective against, and which types of Pokémon it is completely ineffective against.

GET https://pokeapi.co/api/v2/type/{id or name}/

- - 5
		- "ground"
		- ▶
		{} 6 keys
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- ▶
				{} 2 keys
				- "generation-v"
								- "https://pokeapi.co/api/v2/generation/5/"
						- ▶
				{} 6 keys
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- 4
						- ▶
				{} 2 keys
				- "generation-i"
								- "https://pokeapi.co/api/v2/generation/1/"
		- ▶
		{} 2 keys
		- "generation-i"
				- "https://pokeapi.co/api/v2/generation/1/"
		- ▶
		{} 2 keys
		- "physical"
				- "https://pokeapi.co/api/v2/move-damage-class/2/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "ã˜ã‚ã‚“"
						- ▶
				{} 2 keys
				- "ja"
								- "https://pokeapi.co/api/v2/language/1/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- 1
						- ▶
				{} 2 keys
				- "sandshrew"
								- "https://pokeapi.co/api/v2/pokemon/27/"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "sand-attack"
						- "https://pokeapi.co/api/v2/move/28/"

#### Type (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| damage\_relations | A detail of how effective this type is toward others and vice versa. | [TypeRelations](#typerelations) |
| past\_damage\_relations | A list of details of how effective this type was toward others and vice versa in previous generations | list **[TypeRelationsPast](#typerelationspast)* (*[Type](#type)*)* |
| game\_indices | A list of game indices relevent to this item by generation. | list *[GenerationGameIndex](#generationgameindex)* |
| generation | The generation this type was introduced in. | *[NamedAPIResource](#namedapiresource)* (*[Generation](#generation)*) |
| move\_damage\_class | The class of damage inflicted by this type. | *[NamedAPIResource](#namedapiresource)* (*[MoveDamageClass](#movedamageclass)*) |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |
| pokemon | A list of details of Pokémon that have this type. | list *[TypePokemon](#typepokemon)* |
| moves | A list of moves that have this type. | list **[NamedAPIResource](#namedapiresource)* (*[Move](#move)*)* |

#### TypePokemon (type)

| Name | Description | Type |
| --- | --- | --- |
| slot | The order the Pokémon's types are listed in. | *integer* |
| pokemon | The Pokémon that has the referenced type. | *[NamedAPIResource](#namedapiresource)* (*[Pokemon](#pokemon)*) |

#### TypeRelations (type)

| Name | Description | Type |
| --- | --- | --- |
| no\_damage\_to | A list of types this type has no effect on. | list **[NamedAPIResource](#namedapiresource)* (*[Type](#type)*)* |
| half\_damage\_to | A list of types this type is not very effect against. | list **[NamedAPIResource](#namedapiresource)* (*[Type](#type)*)* |
| double\_damage\_to | A list of types this type is very effect against. | list **[NamedAPIResource](#namedapiresource)* (*[Type](#type)*)* |
| no\_damage\_from | A list of types that have no effect on this type. | list **[NamedAPIResource](#namedapiresource)* (*[Type](#type)*)* |
| half\_damage\_from | A list of types that are not very effective against this type. | list **[NamedAPIResource](#namedapiresource)* (*[Type](#type)*)* |
| double\_damage\_from | A list of types that are very effective against this type. | list **[NamedAPIResource](#namedapiresource)* (*[Type](#type)*)* |

#### TypeRelationsPast (type)

| Name | Description | Type |
| --- | --- | --- |
| generation | The last generation in which the referenced type had the listed damage relations | *[NamedAPIResource](#namedapiresource)* (*[Generation](#generation)*) |
| damage\_relations | The damage relations the referenced type had up to and including the listed generation | [TypeRelations](#typerelations) |

## Utility (group)

### Languages (endpoint)

Languages for translations of API resource information.

GET https://pokeapi.co/api/v2/language/{id or name}/

- - 1
		- "ja"
		- true
		- "ja"
		- "jp"
		- ▶
		\[\] 1 item
		- ▶
			{} 2 keys
			- "Japanese"
						- ▶
				{} 2 keys
				- "en"
								- "https://pokeapi.co/api/v2/language/9/"

#### Language (type)

| Name | Description | Type |
| --- | --- | --- |
| id | The identifier for this resource. | *integer* |
| name | The name for this resource. | *string* |
| official | Whether or not the games are published in this language. | *boolean* |
| iso639 | The two-letter code of the country where this language is spoken. Note that it is not unique. | *string* |
| iso3166 | The two-letter code of the language. Note that it is not unique. | *string* |
| names | The name of this resource listed in different languages. | list *[Name](#name)* |

### Common Models

#### APIResource (type)

| Name | Description | Type |
| --- | --- | --- |
| url | The URL of the referenced resource. | *string* |

#### Description (type)

| Name | Description | Type |
| --- | --- | --- |
| description | The localized description for an API resource in a specific language. | *string* |
| language | The language this name is in. | *[NamedAPIResource](#namedapiresource)* (*[Language](#language)*) |

#### Effect (type)

| Name | Description | Type |
| --- | --- | --- |
| effect | The localized effect text for an API resource in a specific language. | *string* |
| language | The language this effect is in. | *[NamedAPIResource](#namedapiresource)* (*[Language](#language)*) |

#### Encounter (type)

| Name | Description | Type |
| --- | --- | --- |
| min\_level | The lowest level the Pokémon could be encountered at. | *integer* |
| max\_level | The highest level the Pokémon could be encountered at. | *integer* |
| condition\_values | A list of condition values that must be in effect for this encounter to occur. | list **[NamedAPIResource](#namedapiresource)* (*[EncounterConditionValue](#encounterconditionvalue)*)* |
| chance | Percent chance that this encounter will occur. | *integer* |
| method | The method by which this encounter happens. | *[NamedAPIResource](#namedapiresource)* (*[EncounterMethod](#encountermethod)*) |

#### FlavorText (type)

| Name | Description | Type |
| --- | --- | --- |
| flavor\_text | The localized flavor text for an API resource in a specific language. Note that this text is left unprocessed as it is found in game files. This means that it contains special characters that one might want to replace with their visible decodable version. Please check out this [issue](https://github.com/veekun/pokedex/issues/218#issuecomment-339841781) to find out more. | *string* |
| language | The language this name is in. | *[NamedAPIResource](#namedapiresource)* (*[Language](#language)*) |
| version | The game version this flavor text is extracted from. | *[NamedAPIResource](#namedapiresource)* (*[Version](#version)*) |

#### GenerationGameIndex (type)

| Name | Description | Type |
| --- | --- | --- |
| game\_index | The internal id of an API resource within game data. | *integer* |
| generation | The generation relevent to this game index. | *[NamedAPIResource](#namedapiresource)* (*[Generation](#generation)*) |

#### MachineVersionDetail (type)

| Name | Description | Type |
| --- | --- | --- |
| machine | The machine that teaches a move from an item. | *[APIResource](#apiresource)* (*[Machine](#machine)*) |
| version\_group | The version group of this specific machine. | *[NamedAPIResource](#namedapiresource)* (*[VersionGroup](#versiongroup)*) |

#### Name (type)

| Name | Description | Type |
| --- | --- | --- |
| name | The localized name for an API resource in a specific language. | *string* |
| language | The language this name is in. | *[NamedAPIResource](#namedapiresource)* (*[Language](#language)*) |

#### NamedAPIResource (type)

| Name | Description | Type |
| --- | --- | --- |
| name | The name of the referenced resource. | *string* |
| url | The URL of the referenced resource. | *string* |

#### VerboseEffect (type)

| Name | Description | Type |
| --- | --- | --- |
| effect | The localized effect text for an API resource in a specific language. | *string* |
| short\_effect | The localized effect text in brief. | *string* |
| language | The language this effect is in. | *[NamedAPIResource](#namedapiresource)* (*[Language](#language)*) |

#### VersionEncounterDetail (type)

| Name | Description | Type |
| --- | --- | --- |
| version | The game version this encounter happens in. | *[NamedAPIResource](#namedapiresource)* (*[Version](#version)*) |
| max\_chance | The total percentage of all encounter potential. | *integer* |
| encounter\_details | A list of encounters and their specifics. | list *[Encounter](#encounter)* |

#### VersionGameIndex (type)

| Name | Description | Type |
| --- | --- | --- |
| game\_index | The internal id of an API resource within game data. | *integer* |
| version | The version relevent to this game index. | *[NamedAPIResource](#namedapiresource)* (*[Version](#version)*) |

#### VersionGroupFlavorText (type)

| Name           | Description                                                    | Type                                                                      |
| -------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------- |
| text           | The localized name for an API resource in a specific language. | *string*                                                                  |
| language       | The language this name is in.                                  | *[NamedAPIResource](#namedapiresource)* (*[Language](#language)*)         |
| version\_group | The version group which uses this flavor text.                 | *[NamedAPIResource](#namedapiresource)* (*[VersionGroup](#versiongroup)*) |