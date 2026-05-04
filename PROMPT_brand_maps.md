# Claude Code Prompt — Build/Refresh 10 Brand Portfolio Maps

Paste everything below into Claude Code (run from `C:\Users\acarr\OneDrive\Documents\Claude\Projects\str-comp-maps`).

---

We already have one brand portfolio map live: `brand-capella` (https://acarras92.github.io/str-comp-maps/brand-capella/), built from `brands/capella.json` via `generate_brand_map.py`. The Capella property list has since been revised, so it needs to be regenerated alongside 9 new brands.

I want to refresh Capella and build the same brand map for 9 more luxury brands using the existing infrastructure, deploy them all to GitHub Pages, and refresh the global overview map so every brand shows up.

## What to do

1. **Overwrite `brands/capella.json`** with the revised Capella list below (11 properties, current as of Spring 2026). Then create one JSON file per brand under `brands/` for the 9 new brands using the exact schema (`brand`, `slug`, `color`, `tagline`, `hotels[]` with `name`/`address`/`city`/`country`). Split each address line below into `address` / `city` / `country`. For remote/island properties without a street address, leave `address` empty and put the island/region in `city`.

2. Each brand gets a distinct `color` (hex) that reads cleanly on Google Maps. Use:
   - Capella: `#7c2d12` (keep existing)
   - Rosewood: `#1f2937` (charcoal)
   - Auberge: `#065f46` (forest green)
   - Viceroy: `#7c3aed` (royal purple)
   - One&Only: `#0c4a6e` (deep ocean)
   - Raffles: `#991b1b` (heritage red)
   - Bvlgari: `#a16207` (gold/bronze)
   - St. Regis: `#1e3a8a` (navy)
   - Corinthia: `#92400e` (warm umber)
   - Rocco Forte: `#365314` (olive)

3. Run `python generate_brand_map.py --deploy` to geocode + render + commit + push every brand JSON. (No flag = render all brands; flag deploys.) Geocache (`geocache.json`) is reused, so unchanged hotels are free.

4. Run `python generate_global_map.py` (or whatever the deploy step is in that script) so the global overview at `/global/` includes every brand's pins, with each brand as its own filterable layer. Confirm Capella's pins reflect the new property list (no more Sanya/KL/Maldives, yes Shanghai/Tufu Bay/Taipei/Macau/Kyoto).

5. Update the root `index.html` so all 10 brand maps are listed and linked.

6. Commit and push. Verify each brand URL returns 200:
   - https://acarras92.github.io/str-comp-maps/brand-capella/ (refresh)
   - https://acarras92.github.io/str-comp-maps/brand-rosewood/
   - https://acarras92.github.io/str-comp-maps/brand-auberge/
   - https://acarras92.github.io/str-comp-maps/brand-viceroy/
   - https://acarras92.github.io/str-comp-maps/brand-oneandonly/
   - https://acarras92.github.io/str-comp-maps/brand-raffles/
   - https://acarras92.github.io/str-comp-maps/brand-bvlgari/
   - https://acarras92.github.io/str-comp-maps/brand-stregis/
   - https://acarras92.github.io/str-comp-maps/brand-corinthia/
   - https://acarras92.github.io/str-comp-maps/brand-roccoforte/

7. Report back any hotels that failed to geocode so I can fix the addresses manually.

## Slug naming

| Brand | JSON file | slug field |
|---|---|---|
| Capella | `brands/capella.json` (overwrite) | `brand-capella` |
| Rosewood | `brands/rosewood.json` | `brand-rosewood` |
| Auberge Resorts | `brands/auberge.json` | `brand-auberge` |
| Viceroy | `brands/viceroy.json` | `brand-viceroy` |
| One&Only | `brands/oneandonly.json` | `brand-oneandonly` |
| Raffles | `brands/raffles.json` | `brand-raffles` |
| Bvlgari | `brands/bvlgari.json` | `brand-bvlgari` |
| St. Regis | `brands/stregis.json` | `brand-stregis` |
| Corinthia | `brands/corinthia.json` | `brand-corinthia` |
| Rocco Forte | `brands/roccoforte.json` | `brand-roccoforte` |

## Taglines (use verbatim)

- Capella — "Capella Hotels & Resorts — ultra-luxury portfolio (11 properties)"
- Rosewood — "Rosewood Hotels & Resorts — 38 properties in 23 countries"
- Auberge — "Auberge Resorts Collection — independent luxury, US-led with international expansion"
- Viceroy — "Viceroy Hotels & Resorts — design-forward modern luxury"
- One&Only — "One&Only Resorts — ultra-private destination luxury"
- Raffles — "Raffles Hotels & Resorts — colonial-heritage luxury (Accor)"
- Bvlgari — "Bvlgari Hotels & Resorts — ultra-exclusive, sub-100 keys"
- St. Regis — "The St. Regis — Marriott's flagship luxury brand, 61 properties (WGT comp)"
- Corinthia — "Corinthia Hotels — European capital-city luxury"
- Rocco Forte — "Rocco Forte Hotels — family-run UK/Italian luxury"

## Brand data

### CAPELLA HOTELS & RESORTS (11 — overwrite existing JSON)
- Capella Singapore — 1 The Knolls, Sentosa Island, Singapore 098297
- Capella Bangkok — 300/2 Charoenkrung Road, Yannawa, Sathorn, Bangkok 10120, Thailand
- Capella Hanoi — 11 P. Lê Phụng Hiểu, Hoan Kiem District, Hanoi 100000, Vietnam
- Capella Sydney — 1 Bridge Street, Sydney NSW 2000, Australia
- Capella Ubud, Bali — Jalan Raya Keliki, Tegallalang, Ubud, Gianyar, Bali, Indonesia
- Capella Shanghai — 480 Fenyang Road, Xuhui District, Shanghai 200031, China
- Capella Tufu Bay, Hainan — Tufu Bay, Wanning City, Hainan Province, China
- Capella Taipei — No. 88 Songgao Road, Xinyi District, Taipei 110, Taiwan
- Capella Tokyo — Tokyo Midtown Hibiya, 1-1-2 Yurakucho, Chiyoda-ku, Tokyo 100-0006, Japan
- Capella at Galaxy Macau — Galaxy Macau, Estrada da Baía de Nossa Senhora da Esperança, Cotai, Macao
- Capella Kyoto — Miyagawa-cho District, Higashiyama, Kyoto, Japan

### ROSEWOOD HOTELS & RESORTS (38)
- The Carlyle, A Rosewood Hotel — 35 East 76th Street, New York, NY 10021, USA
- Rosewood Mansion on Turtle Creek — 2821 Turtle Creek Boulevard, Dallas, TX 75219, USA
- Rosewood Miramar Beach — 1759 S Jameson Lane, Montecito, CA 93108, USA
- Rosewood Sand Hill — 2825 Sand Hill Road, Menlo Park, CA 94025, USA
- Rosewood Washington, D.C. — 1050 31st Street NW, Georgetown, Washington, DC 20007, USA
- Rosewood Inn of the Anasazi — 113 Washington Avenue, Santa Fe, NM 87501, USA
- Rosewood CordeValle — One CordeValle Club Drive, San Martin, CA 95046, USA
- Kona Village, A Rosewood Resort — 72-300 Maheawalu Drive, Kailua-Kona, HI 96740, USA
- Rosewood Hotel Georgia — 801 West Georgia Street, Vancouver, BC V6C 1P7, Canada
- Rosewood Bermuda — Tucker's Town, Smith's Parish HS02, Bermuda
- Rosewood Le Guanahani St. Barth — Grand Cul de Sac, 97133 Saint Barthélemy, French West Indies
- Rosewood Baha Mar — One Baha Mar Boulevard, Nassau, Bahamas
- Rosewood Little Dix Bay — Spring Bay Road, Virgin Gorda, British Virgin Islands
- Rosewood Mayakoba — Carretera Federal Cancún–Playa del Carmen KM 298, Q. Roo 77710, Mexico
- Rosewood Mandarina — Riviera Nayarit, Municipio de Bahía de Banderas, Nayarit, Mexico
- Rosewood San Miguel de Allende — Nemesio Diez 11, Centro, San Miguel de Allende, GTO 37700, Mexico
- Las Ventanas al Paraíso, A Rosewood Resort — Carretera Transpeninsular KM 19.5, San José del Cabo, BCS, Mexico
- Hôtel de Crillon, A Rosewood Hotel — 10 Place de la Concorde, 75008 Paris, France
- Rosewood London — 252 High Holborn, London WC1V 7EN, UK
- Rosewood Munich — Maximilianstrasse 2, 80539 Munich, Germany
- Rosewood Vienna — Petersplatz 7, 1010 Vienna, Austria
- Rosewood Villa Magna — Paseo de la Castellana 22, 28046 Madrid, Spain
- Rosewood Castiglion del Bosco — Loc. Castiglion del Bosco, 53024 Montalcino (SI), Italy
- Rosewood Schloss Fuschl — Schloss Fuschl 1, 5322 Hof bei Salzburg, Austria
- Rosewood Hong Kong — 18 Salisbury Road, Tsim Sha Tsui, Kowloon, Hong Kong
- Rosewood Beijing — Jiangtai Road, Chaoyang District, Beijing 100015, China
- Rosewood Guangzhou — 111 Lihua Street, Tianhe District, Guangzhou 510623, China
- Rosewood Bangkok — 1041/38 Ploenchit Road, Lumpini, Pathumwan, Bangkok 10330, Thailand
- Rosewood Phuket — 88/28 Muen-Ngoen Road, Patong, Phuket 83150, Thailand
- Rosewood Phnom Penh — Vattanac Capital Tower, 66 Monivong Boulevard, Phnom Penh, Cambodia
- Rosewood Luang Prabang — Ban Xieng Mouane, Luang Prabang 0600, Lao PDR
- Rosewood Miyakojima — 1190-1 Shimozato, Miyakojima City, Okinawa 906-0000, Japan
- Rosewood São Paulo — Alameda Santos 2233, Cerqueira César, São Paulo 01419-100, Brazil
- Rosewood Abu Dhabi — Al Maryah Island, Abu Dhabi, UAE
- Rosewood Doha — Musheirib, Doha, Qatar
- Rosewood Riyadh — Olaya Street, Al Olaya District, Riyadh 12214, Saudi Arabia
- Rosewood Cape Kidnappers — 448 Te Awanga Road, Hawke's Bay 4171, New Zealand
- Rosewood Matakauri — Glenorchy Road, Queenstown 9371, New Zealand

### AUBERGE RESORTS COLLECTION (28)
- Auberge du Soleil — 180 Rutherford Hill Road, Rutherford, CA 94573, USA
- Solage Calistoga — 755 Silverado Trail North, Calistoga, CA 94515, USA
- Stanly Ranch — 2671 Stanly Crossroad, Napa, CA 94559, USA
- Inn at Mattei's Tavern — 2350 Railway Avenue, Los Olivos, CA 93441, USA
- Hotel Jerome — 330 East Main Street, Aspen, CO 81611, USA
- Madeline Hotel & Residences — 568 Mountain Village Boulevard, Telluride, CO 81435, USA
- Element 52 — 117 Lost Creek Lane, Telluride, CO 81435, USA
- The Lodge at Blue Sky — 4200 Old Ranch Road, Park City, UT 84098, USA
- Goldener Hirsch — 7570 Royal Street East, Park City, UT 84060, USA
- Sleeping Indian Lodge — 5765 County Road 24, Ridgway, CO 81432, USA
- Bishop's Lodge — 1297 Bishop's Lodge Road, Santa Fe, NM 87506, USA
- Commodore Perry Estate — 4100 Red River Street, Austin, TX 78751, USA
- Bowie House — 401 West Magnolia Avenue, Fort Worth, TX 76104, USA
- Primland Resort — 2000 Primland Drive, Meadows of Dan, VA 24120, USA
- The Dunlin — 2650 Chisolm Road, Johns Island, SC 29455, USA
- The Vanderbilt — 41 Mary Street, Newport, RI 02840, USA
- White Barn Inn — 37 Beach Avenue, Kennebunk, ME 04043, USA
- Mayflower Inn & Spa — 118 Woodbury Road, Washington, CT 06793, USA
- Mauna Lani — 68-1400 Mauna Lani Drive, Kohala Coast, HI 96743, USA
- Esperanza — Carretera Transpeninsular KM 7, Los Cabos, BCS, Mexico
- Chileno Bay — Carretera Transpeninsular KM 15, Los Cabos, BCS, Mexico
- Susurros del Corazón — Carretera Federal 200 KM 2.5, Punta de Mita, Nayarit, Mexico
- Etéreo — Carretera Federal 307 KM 47, Riviera Maya, Quintana Roo, Mexico
- Hacienda AltaGracia — La Cangreja, Pérez Zeledón, San José, Costa Rica
- Collegio alla Querce — Via Bolognese 52, 50139 Florence, Italy
- Domaine des Etangs — Massignac, 16310 Charente, France
- Grace Santorini — Imerovigli, 847 00 Santorini, Greece
- The Woodward — Quai Wilson 1, 1201 Geneva, Switzerland

### VICEROY HOTELS & RESORTS (12)
- Viceroy Santa Monica — 1819 Ocean Avenue, Santa Monica, CA 90401, USA
- Viceroy L'Ermitage Beverly Hills — 9291 Burton Way, Beverly Hills, CA 90210, USA
- Viceroy Chicago — 1118 North State Street, Chicago, IL 60610, USA
- Viceroy Washington DC — 1430 Rhode Island Avenue NW, Washington, DC 20005, USA
- Viceroy Snowmass — 130 Wood Road, Snowmass Village, CO 81615, USA
- Viceroy Dorado Beach — 100 Dorado Beach Drive, Dorado, Puerto Rico 00646
- Viceroy Los Cabos — Paseo Malecon San Jose Lote 8, San José del Cabo, BCS 23405, Mexico
- Viceroy Riviera Maya — Playa Xcalacoco Frac 7, Playa del Carmen, Q. Roo 77710, Mexico
- Viceroy at Ombria Algarve — Rua da Ombria Nr 9, 8100-396 Tôr, Loulé, Algarve, Portugal
- Viceroy St. Lucia — Val des Pitons, La Baie de Silence, Soufrière, Saint Lucia
- Viceroy Kopaonik — Brzeće 36354, Kopaonik, Serbia
- Viceroy Alula — AlUla Old Town, AlUla, Medina Province, Saudi Arabia

### ONE&ONLY RESORTS (14)
- One&Only Palmilla — Carretera Transpeninsular KM 7.5 Punta Palmilla, San José del Cabo, BCS, Mexico
- One&Only Mandarina — Riviera Nayarit, Municipio de Bahía de Banderas, Nayarit, Mexico
- One&Only Moonlight Basin — 50 Moonlight Basin Road, Big Sky, MT 59716, USA
- One&Only Royal Mirage — Al Sufouh Road, Dubai 37252, UAE
- One&Only The Palm — East Crescent Road, Palm Jumeirah, Dubai, UAE
- One&Only Za'abeel — Sheikh Zayed Road, Za'abeel, Dubai, UAE
- One&Only Portonovi — Valdanos Bay, Boka Bay, Herceg Novi, Montenegro
- One&Only Kéa Island — Vourkari, Kéa Island, Cyclades, Greece
- One&Only Aesthesis — Kavouri, Vouliagmeni, Athens 16671, Greece
- One&Only Cape Town — Dock Road, V&A Waterfront, Cape Town 8001, South Africa
- One&Only Reethi Rah — North Malé Atoll, Republic of Maldives
- One&Only Le Saint Géran — Pointe de Flacq, Mauritius
- One&Only Nyungwe House — Nyungwe National Park, Southern Rwanda
- One&Only Gorilla's Nest — Kinigi, Volcanoes National Park, Northern Rwanda

### RAFFLES HOTELS & RESORTS (16)
- Raffles Singapore — 1 Beach Road, Singapore 189673
- Raffles Sentosa Resort & Spa — 101 Siloso Road, Sentosa, Singapore 098970
- Raffles Boston — 40 Trinity Place, Back Bay, Boston, MA 02116, USA
- Le Royal Monceau – Raffles Paris — 37 Avenue Hoche, 75008 Paris, France
- Raffles London at The OWO — 57 Whitehall, London SW1A 2BX, UK
- Raffles Warsaw — Grzybowska 45, 00-844 Warsaw, Poland
- Raffles Istanbul — Zorlu Center, Levazım Mah. Vadi Caddesi, Beşiktaş, 34340 Istanbul, Turkey
- Raffles Doha — Marina East Street, Lusail Marina District, Lusail City, Doha, Qatar
- Raffles Al Areen Palace Bahrain — Zallaq Highway, Sakhir, Bahrain
- Raffles The Palm Dubai — East Crescent Road, Palm Jumeirah, Dubai, UAE
- Raffles Udaipur — Shiv Sagar Island, Udaipur, Rajasthan 313001, India
- Raffles Jaipur — Khasa Kothi Circle, MI Road, Jaipur, Rajasthan 302001, India
- Raffles Shenzhen — One Shenzhen Bay, Nanshan District, Shenzhen 518054, China
- Raffles Hainan — Boao, Qionghai City, Hainan Province, China
- Raffles Bali — Jalan Karang Mas Sejahtera, Jimbaran, Bali 80361, Indonesia
- Raffles Maldives Meradhoo Resort — Meradhoo Island, Gaafu Alifu Atoll, Maldives

### BVLGARI HOTELS & RESORTS (9)
- Bvlgari Hotel Milano — Via Privata Fratelli Gabba 7b, 20121 Milan, Italy
- Bvlgari Hotel London — 171 Knightsbridge, London SW7 1DW, UK
- Bvlgari Hotel Paris — 30 Avenue George V, 75008 Paris, France
- Bvlgari Hotel Roma — Piazza Augusto Imperatore 10, 00186 Rome, Italy
- Bvlgari Resort Bali — Jalan Goa Lempeh, Uluwatu, Kuta Selatan, Bali 80364, Indonesia
- Bvlgari Resort Dubai — Jumeira Bay Island, Jumeirah 2, Dubai, UAE
- Bvlgari Hotel Beijing — 6 East Chang'an Avenue, Dongcheng District, Beijing 100006, China
- Bvlgari Hotel Shanghai — 33 The Bund, Zhongshan East No. 1 Road, Huangpu District, Shanghai 200002, China
- Bvlgari Hotel Tokyo — Tokyo Midtown Yaesu, 2-2-1 Yaesu, Chuo-ku, Tokyo 104-0028, Japan

### ST. REGIS HOTELS & RESORTS (61 — Marriott full portfolio)
- The St. Regis New York — 2 East 55th Street at Fifth Avenue, New York, NY 10022, USA
- The St. Regis Chicago — 401 East Upper Wacker Drive, Chicago, IL 60601, USA
- The St. Regis Atlanta — 88 West Paces Ferry Road NW, Atlanta, GA 30305, USA
- The St. Regis Washington, D.C. — 923 16th & K Street NW, Washington, DC 20006, USA
- The St. Regis San Francisco — 125 Third Street, San Francisco, CA 94103, USA
- The St. Regis Aspen Resort — 315 Dean Street, Aspen, CO 81611, USA
- The St. Regis Bal Harbour Resort — 9703 Collins Avenue, Bal Harbour, FL 33154, USA
- The St. Regis Longboat Key Resort — 1620 Gulf of Mexico Drive, Longboat Key, FL 34228, USA
- The St. Regis Houston — 1919 Briar Oaks Lane, Houston, TX 77027, USA
- The St. Regis Toronto — 325 Bay Street, Toronto, ON M5H 4G3, Canada
- The St. Regis Bermuda Resort — 6100 Cooper's Island Road, St. George's Parish, Bermuda
- The St. Regis Cap Cana Resort — Cap Cana, Punta Cana, La Altagracia, Dominican Republic
- The St. Regis Aruba Resort — L.G. Smith Boulevard 82, Noord, Aruba
- The St. Regis Costa Mujeres Resort — Carretera Cancún–Punta Sam KM 19.8, Cancún, Q. Roo, Mexico
- The St. Regis Kanai Resort, Riviera Maya — Playa del Carmen, Riviera Maya, Quintana Roo, Mexico
- The St. Regis Mexico City — Paseo de la Reforma 439, Cuauhtémoc, CDMX 06600, Mexico
- The St. Regis Punta Mita Resort — Carretera a Punta de Mita KM 9, Bahía de Banderas, Nayarit 63734, Mexico
- The St. Regis Florence — Piazza Ognissanti 1, 50123 Florence, Italy
- The St. Regis Rome — Via Vittorio Emanuele Orlando 3, 00185 Rome, Italy
- The St. Regis Venice — San Marco 2159, 30124 Venice, Italy
- The St. Regis Budapest — Andrássy Avenue 5-7, Budapest 1061, Hungary
- The St. Regis Belgrade — Vladimira Popovića 10, Novi Beograd, Belgrade 11070, Serbia
- The St. Regis Mardavall Mallorca Resort — Carretera d'Andratx 19, 07181 Es Capdellà, Mallorca, Spain
- The St. Regis Istanbul — Suzer Plaza, Askerocağı Caddesi 15, Şişli, Istanbul 34367, Turkey
- The St. Regis Abu Dhabi — Nation Towers, Corniche Road, Abu Dhabi, UAE
- The St. Regis Saadiyat Island Resort — Saadiyat Island, Abu Dhabi, UAE
- The St. Regis Dubai, The Palm — East Crescent Road, Palm Jumeirah, Dubai, UAE
- The St. Regis Downtown Dubai — The Burj Vista, Downtown Dubai, UAE
- The St. Regis Doha — Doha West Bay, Diplomatic Area, Doha, Qatar
- The St. Regis Marsa Arabia Island — The Pearl-Qatar, Doha, Qatar
- The St. Regis Riyadh — 2941 Makkah Al Mukarramah Road, Riyadh 12241, Saudi Arabia
- The St. Regis Red Sea Resort — NEOM / Red Sea Project, Tabuk Province, Saudi Arabia
- The St. Regis Kuwait — Arabian Gulf Street, Salmiya, Kuwait City, Kuwait
- The St. Regis Al Mouj Muscat Resort — Al Mouj Marina, Muscat, Oman
- The St. Regis Amman — King Abdullah II Street, Shmeisani, Amman 11190, Jordan
- The St. Regis Cairo — 1113 Corniche El Nil, Maadi, Cairo 11431, Egypt
- The St. Regis New Capital, Cairo — New Administrative Capital, Cairo Governorate, Egypt
- The St. Regis Le Morne Resort — Le Morne Peninsula, District de la Rivière Noire, Mauritius
- The St. Regis La Bahia Blanca Resort — Tamuda Bay, Fnideq, Tetouan Province, Morocco
- The St. Regis Beijing — 21 Jianguomenwai Avenue, Chaoyang District, Beijing 100020, China
- The St. Regis Shanghai Jingan — 1008 Beijing West Road, Jing'an District, Shanghai 200040, China
- The St. Regis on the Bund, Shanghai — 123 Xingye Road, Huangpu District, Shanghai 200021, China
- The St. Regis Shenzhen — 5016 Shennan East Road, Luohu District, Shenzhen 518001, China
- The St. Regis Shenzhen Bao'an — Bao'an District, Shenzhen, Guangdong, China
- The St. Regis Zhuhai — Jingshan Road, Xiangzhou District, Zhuhai 519000, China
- The St. Regis Tianjin — 188 Zijin Mountain Road, Hexi District, Tianjin 300222, China
- The St. Regis Chengdu — 88 Renmin South Road, Wuhou District, Chengdu 610041, China
- The St. Regis Changsha — Wujialing Area, Kaifu District, Changsha, Hunan 410008, China
- The St. Regis Qingdao — 9 Donghai West Road, Shinan District, Qingdao 266071, China
- The St. Regis Sanya Yalong Bay Resort — Yalong Bay National Resort District, Sanya, Hainan 572000, China
- The St. Regis Macao — The Parisian Macao, Estrada do Istmo, Cotai Strip, Macao
- The St. Regis Hong Kong — 19 Harbour Road, Wan Chai, Hong Kong
- The St. Regis Lhasa Resort — Lhasa Lu, Chengguan District, Lhasa, Tibet 850000, China
- The St. Regis Singapore — 29 Tanglin Road, Singapore 247911
- The St. Regis Bangkok — 159 Rajadamri Road, Pathumwan, Bangkok 10330, Thailand
- The St. Regis Kuala Lumpur — Jalan Stesen Sentral 2, KL Sentral, 50470 Kuala Lumpur, Malaysia
- The St. Regis Langkawi — Jalan Pantai Beringin, 07000 Langkawi, Kedah, Malaysia
- The St. Regis Jakarta — Jl. Gatot Subroto Kav. 18, SCBD, South Jakarta 12710, Indonesia
- The St. Regis Bali Resort — Kawasan Pariwisata Nusa Dua Lot S6, 80363 Nusa Dua, Bali, Indonesia
- The St. Regis Goa Resort — Arossim Beach, Cansaulim, South Goa 403712, India
- The St. Regis Mumbai — 462 Senapati Bapat Marg, Lower Parel, Mumbai 400013, India
- The St. Regis Osaka — 3-6-12 Honmachi, Chuo-ku, Osaka 541-0053, Japan
- The St. Regis Astana — Khan Shatyr, Astana 010000, Kazakhstan
- The St. Regis Bora Bora Resort — Motu Ome'e, Bora Bora 98730, French Polynesia
- The St. Regis Maldives Vommuli Resort — Vommuli Island, Dhaalu Atoll 13080, Maldives

### CORINTHIA HOTELS (10)
- Corinthia London — Whitehall Place, London SW1A 2BD, UK
- Corinthia Brussels (Grand Hotel Astoria) — 101–103 Rue Royale, 1000 Brussels, Belgium
- Corinthia Rome — Piazza del Parlamento 18, 00186 Rome, Italy
- Corinthia Budapest — Erzsébet körút 43–49, Budapest H-1073, Hungary
- Corinthia Prague — Kongresová 1, 140 00 Praha 4, Czech Republic
- Corinthia Lisbon — Av. Columbano Bordalo Pinheiro 105, 1099-031 Lisbon, Portugal
- Corinthia St. Petersburg — Nevsky Prospect 57, St. Petersburg 191025, Russia
- Corinthia St George's Bay, Malta — St George's Bay, St Julian's STJ 3301, Malta
- Corinthia Palace, Malta — De Paule Avenue, Balzan BZN 9022, Malta
- Corinthia Tripoli — Dat Al-Imad Complex, Tower 4, Tripoli, Libya

### ROCCO FORTE HOTELS (14)
- Brown's Hotel — 33 Albemarle Street, Mayfair, London W1S 4BP, UK
- The Balmoral — 1 Princes Street, Edinburgh EH2 2EQ, UK
- Rocco Forte House — 70 St James's Street, London SW1A 1LE, UK
- Hotel de Russie — Via del Babuino 9, 00187 Rome, Italy
- Hotel de La Ville — Via Sistina 69, 00187 Rome, Italy
- Hotel Savoy — Piazza della Repubblica 7, 50123 Florence, Italy
- Verdura Resort — SS 115 KM 131, 92100 Sciacca, Sicily, Italy
- Masseria Torre Maizza — Savelletri di Fasano, 72010 Brindisi, Puglia, Italy
- Hotel Amigo — Rue de l'Amigo 1–3, 1000 Brussels, Belgium
- Hotel de Rome — Behrenstrasse 37, 10117 Berlin, Germany
- The Charles Hotel — Sophienstrasse 28, 80333 Munich, Germany
- Villa Kennedy — Kennedyallee 70, 60596 Frankfurt am Main, Germany
- Hotel Astoria — Bolshaya Morskaya Street 39, St. Petersburg 190000, Russia
- Palazzo Sirignano — Via Sirignano 11, 80121 Naples, Italy

---

When you're done, post:
1. The 10 deployed URLs (Capella refreshed + 9 new).
2. Any hotels that failed to geocode (so I can fix manually).
3. Confirmation that the global map and root index now include all 10 brands and that Capella's revised property list is reflected in both.

Total properties across all 10 brands: ~213.
