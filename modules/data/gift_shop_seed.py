"""
Gift Shop demo seed — initializes the in-memory store with the
The Bay Street Mercantile starting catalog: Lowcountry food, branded merch,
local artist consignments, the Comphy resell program, the Murano
glass partnership with Gino Mazzuccato, and SC wines & spirits.
"""
from __future__ import annotations


def init_demo_gift_shop() -> dict:
    """Returns {category_id: category_dict} with seeded items."""
    return {
        "lowcountry_food": {
            "id": "lowcountry_food",
            "icon": "🍯",
            "name": "Lowcountry Food & Pantry",
            "description": "Local flavors of the South Carolina Lowcountry",
            "arrangement": "owned",
            "fulfillment": "in_person",
            "margin": 0.55,
            "active": True,
            "sort_order": 1,
            "notes": "",
            "items": [
                {"id":"lc_001","name":"Sweetgrass Strawberry Fig Jam","price":12.00,"cost":5.40,"monthly_units":28,"active":True,"notes":"Local farm sourced","vendor":"Sweetgrass Farm, Beaufort SC"},
                {"id":"lc_002","name":"Lowcountry Raw Honey","price":18.00,"cost":8.10,"monthly_units":15,"active":True,"notes":"","vendor":"Beaufort Bee Company"},
                {"id":"lc_003","name":"Stone-Ground White Grits","price":9.00,"cost":4.05,"monthly_units":20,"active":True,"notes":"","vendor":"Geechee Boy Mill"},
                {"id":"lc_004","name":"Pecan Pralines (3-pack)","price":8.00,"cost":3.60,"monthly_units":32,"active":True,"notes":"Top seller","vendor":"Local confectioner"},
                {"id":"lc_005","name":"Beaufort Hot Sauce","price":10.00,"cost":4.50,"monthly_units":18,"active":True,"notes":"","vendor":"Lowcountry Sauce Co."},
            ],
        },
        "branded": {
            "id": "branded",
            "icon": "👕",
            "name": "Bay Street Inn Branded",
            "description": "Merchandise branded with the Bay Street Inn name",
            "arrangement": "owned",
            "fulfillment": "in_person",
            "margin": 0.70,
            "active": True,
            "sort_order": 2,
            "notes": "",
            "items": [
                {"id":"br_001","name":"Embroidered Baseball Cap","price":32.00,"cost":9.60,"monthly_units":8,"active":True,"notes":"Navy with gold embroidery","vendor":"Local embroidery shop"},
                {"id":"br_002","name":"Canvas Tote Bag","price":28.00,"cost":8.40,"monthly_units":12,"active":True,"notes":"","vendor":""},
                {"id":"br_003","name":"Ceramic Coffee Mug","price":22.00,"cost":6.60,"monthly_units":18,"active":True,"notes":"Bestseller","vendor":""},
                {"id":"br_004","name":"Soy Candle – Bay Breeze Scent","price":24.00,"cost":7.20,"monthly_units":10,"active":True,"notes":"","vendor":""},
            ],
        },
        "local_art": {
            "id": "local_art",
            "icon": "🎨",
            "name": "Local Artist Collection",
            "description": ("Original work by Beaufort and Lowcountry artists. "
                            "Paintings hang throughout the inn — all available for purchase."),
            "arrangement": "consignment",
            "fulfillment": "in_person",
            "margin": 0.30,
            "active": True,
            "sort_order": 3,
            "consignment_details": {
                "inn_commission_pct": 30,
                "artist_pct": 70,
                "payment_terms": "Monthly settlement to each artist",
                "display_agreement": ("Artist provides framed work, inn displays prominently, "
                                       "replaces sold pieces within 2 weeks"),
            },
            "notes": ("All pieces displayed throughout inn. Guests may purchase any displayed "
                      "artwork. Replace within 14 days of sale."),
            "items": [
                {"id":"art_001","name":"Beaufort Waterfront at Dusk – Original Oil","price":485.00,"cost":0,"monthly_units":1,"active":True,"notes":"24x36 original oil, Room 201 above fireplace","vendor":"Sarah Middleton, Beaufort SC","is_consignment":True},
                {"id":"art_002","name":"Gullah Heritage Series – Print (signed)","price":145.00,"cost":0,"monthly_units":2,"active":True,"notes":"Limited edition signed prints, 5 available","vendor":"James Frazier, Beaufort SC","is_consignment":True},
                {"id":"art_003","name":"Sweetgrass Basket (large, handwoven)","price":285.00,"cost":0,"monthly_units":1,"active":True,"notes":"Traditional Gullah Geechee craft, lobby display","vendor":"Mary Campbell, St. Helena Island","is_consignment":True},
                {"id":"art_004","name":"Sea Glass & Driftwood Sculpture","price":165.00,"cost":0,"monthly_units":1,"active":True,"notes":"Each piece unique","vendor":"Local coastal artist","is_consignment":True},
            ],
        },
        "comphy_bedding": {
            "id": "comphy_bedding",
            "icon": "🛏️",
            "name": "Comphy Luxury Bedding",
            "description": ("The same ultra-soft bedding on your bed tonight. Comphy's signature "
                            "micro-fiber sheets, duvet covers, and pillowcases available to order for your home."),
            "arrangement": "resell",
            "fulfillment": "drop_ship",
            "margin": 0.25,
            "active": True,
            "sort_order": 4,
            "resell_details": {
                "brand":          "Comphy",
                "program_name":   "Comphy Resell Program",
                "account_rep":    "",
                "website":        "comphy.com",
                "ordering":       ("Orders placed through Comphy wholesale portal. "
                                    "Ships direct to guest's home."),
                "min_order":      None,
                "lead_time":      "5-7 business days standard shipping",
                "notes":          ("Guests love the bedding. Offer order cards in every room "
                                    "with QR code linking to order page."),
            },
            "notes": ("Place Comphy order cards in every room. QR code links to your inn's "
                      "custom order page. Commission credited monthly by Comphy."),
            "items": [
                {"id":"cm_001","name":"Comphy Sheet Set – Queen","price":189.00,"cost":142.00,"monthly_units":3,"active":True,"notes":"Most popular size","vendor":"Comphy","fulfillment":"drop_ship"},
                {"id":"cm_002","name":"Comphy Sheet Set – King","price":209.00,"cost":157.00,"monthly_units":2,"active":True,"notes":"","vendor":"Comphy","fulfillment":"drop_ship"},
                {"id":"cm_003","name":"Comphy Duvet Cover – Queen","price":145.00,"cost":109.00,"monthly_units":2,"active":True,"notes":"","vendor":"Comphy","fulfillment":"drop_ship"},
                {"id":"cm_004","name":"Comphy Pillowcase Pair","price":65.00,"cost":49.00,"monthly_units":4,"active":True,"notes":"Great add-on gift","vendor":"Comphy","fulfillment":"drop_ship"},
            ],
        },
        "murano_glass": {
            "id": "murano_glass",
            "icon": "🫧",
            "name": "Murano Glass Collection",
            "description": ("Authentic handblown Murano glass from Gino Mazzuccato, Murano Island, Italy. "
                            "Each piece is a unique work of art made using centuries-old Venetian "
                            "glassblowing techniques."),
            "arrangement": "resell",
            "fulfillment": "drop_ship",
            "margin": 0.35,
            "active": True,
            "sort_order": 5,
            "resell_details": {
                "brand":            "Gino Mazzuccato",
                "program_name":     "Mazzuccato Authorized Reseller",
                "factory":          "Fondamenta Manin 1, Murano, Venice, Italy",
                "contact_marketing":"marketing@ginomazzuccato.com",
                "contact_sales":    "sales@ginomazzuccato.com",
                "website":          "ginomazzuccato.com",
                "ordering":         ("Email orders to sales@ginomazzuccato.com or through partner portal. "
                                      "Ships from Murano."),
                "lead_time":        "3-5 weeks from Murano",
                "shipping_notes":   ("All pieces individually packed and insured for transit. "
                                      "Drop-ship to guest home or inn for in-person purchase."),
                "display":          ("Display 3-5 showcase pieces in inn lobby or common areas. "
                                      "Photographed pieces available for immediate drop-ship order."),
            },
            "notes": ("Display 3-5 signature pieces throughout inn with small cards explaining the "
                      "Murano Island heritage. All items available for purchase — ships direct from "
                      "the Mazzuccato factory in Murano, Italy (3-5 weeks). Story: the owners visited "
                      "Venice in 2025 and brought this partnership back to Beaufort."),
            "items": [
                {"id":"mg_001","name":"Murano Millefiori Vase – Medium","price":285.00,"cost":188.00,"monthly_units":1,"active":True,"notes":"Lobby display piece. Order ships from Italy.","vendor":"Gino Mazzuccato","fulfillment":"drop_ship"},
                {"id":"mg_002","name":"Murano Wine Glasses – Set of 2","price":195.00,"cost":129.00,"monthly_units":1,"active":True,"notes":"Paired with Romance/Anniversary packages","vendor":"Gino Mazzuccato","fulfillment":"drop_ship"},
                {"id":"mg_003","name":"Murano Paperweight – Aqua Floral","price":125.00,"cost":82.00,"monthly_units":2,"active":True,"notes":"Accessible price point, popular gift","vendor":"Gino Mazzuccato","fulfillment":"drop_ship"},
                {"id":"mg_004","name":"Murano Pendant Necklace","price":165.00,"cost":109.00,"monthly_units":1,"active":True,"notes":"Wearable art — unique gift","vendor":"Gino Mazzuccato","fulfillment":"drop_ship"},
                {"id":"mg_005","name":"Murano Blown Glass Bowl – Venetian Gold","price":345.00,"cost":228.00,"monthly_units":1,"active":True,"notes":"Statement piece, display in dining room","vendor":"Gino Mazzuccato","fulfillment":"drop_ship"},
            ],
        },
        "wines_spirits": {
            "id": "wines_spirits",
            "icon": "🍷",
            "name": "Wines & Spirits",
            "description": "South Carolina wines, spirits, and craft ales",
            "arrangement": "owned",
            "fulfillment": "in_person",
            "margin": 0.40,
            "active": True,
            "sort_order": 6,
            "notes": "Requires SC liquor license compliance. Verify current licensing before selling.",
            "items": [
                {"id":"ws_001","name":"SC Muscadine Wine – Red","price":22.00,"cost":13.20,"monthly_units":18,"active":True,"notes":"Local vineyard","vendor":""},
                {"id":"ws_002","name":"Firefly Sweet Tea Vodka","price":28.00,"cost":16.80,"monthly_units":12,"active":True,"notes":"SC distillery — requires license","vendor":"Firefly"},
                {"id":"ws_003","name":"Local Craft Ale 4-Pack","price":16.00,"cost":9.60,"monthly_units":15,"active":True,"notes":"","vendor":""},
            ],
        },
    }
