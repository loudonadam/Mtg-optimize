# Resources for rules-aware Magic simulations

If we need stronger rules enforcement without implementing every corner case by hand, these libraries and APIs can help:

- **Scryfall API**: Comprehensive, actively maintained card database with rules text, mana costs, and oracle rulings. Great for fetching authoritative card details and legality data on demand. Docs: https://scryfall.com/docs/api
- **MTGJSON**: Offline-friendly JSON datasets of the full card catalog, including mana costs, types, and rulings. Suitable for seeding local caches and validating card properties. Docs: https://mtgjson.com
- **mtg-sdk-python**: Lightweight Python wrapper around Magic's REST API (now backed by magicthegathering.io data) that simplifies card lookups. Useful for prototyping, though the underlying dataset is not as current as Scryfall's. PyPI: https://pypi.org/project/mtgsdk/
- **scrython**: Python client for Scryfall that handles pagination and object shaping. Good for scripting data pulls for validation or simulation inputs. PyPI: https://pypi.org/project/Scrython/
- **Cockatrice card database**: Open-source XML card database used by the Cockatrice client. While not a rules engine, the structured data can supplement offline validation. Project: https://github.com/Cockatrice/Cockatrice
- **Magarena / Forge rules engines**: Open-source digital implementations of Magic that include robust rules engines. Their source code (Java) can serve as a reference for sequencing, mana payments, and comprehensive rules handling if we need deeper correctness guidance. Magarena: https://github.com/magarena/magarena, Forge: https://github.com/Card-Forge/forge

These resources can be combined: for example, using Scryfall or MTGJSON for canonical card attributes and rulings, then borrowing sequencing logic from Forge/Magarena to model tapped lands, mana production, and timing restrictions more faithfully.
