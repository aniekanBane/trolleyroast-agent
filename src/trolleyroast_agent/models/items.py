from typing import NamedTuple


class MonitoredItem(NamedTuple):
    """A tuple representing a monitored item.

    Attributes:
        key: The unique key of the item.
        name: The name of the item.
        category: The category of the item.
    """

    key: str
    name: str
    category: str


STAPLE_ITEMS_LIST = [
    MonitoredItem("milk_semi_4pt", "Semi Skimmed Milk 4pt", "dairy"),
    MonitoredItem("milk_whole_4pt", "Whole Milk 4pt", "dairy"),
    MonitoredItem("butter_250g", "Salted Butter 250g", "dairy"),
    MonitoredItem("cheddar_400g", "Mature Cheddar 400g", "dairy"),
    MonitoredItem("eggs_medium_6", "Eggs Medium 6", "eggs"),
    MonitoredItem("bread_white_800g", "White Sliced Bread 800g", "bakery"),
    MonitoredItem("bread_wholemeal_800g", "Wholemeal Sliced Bread 800g", "bakery"),
    MonitoredItem("chicken_breast_500g", "Chicken Breast 500g", "meat"),
    MonitoredItem("beef_mince_500g", "Beef Mince 500g", "meat"),
    MonitoredItem("potatoes_2_5kg", "Potatoes 2.5kg", "produce"),
    MonitoredItem("apples_6pack", "Apples 6 Pack", "produce"),
    MonitoredItem("bananas_kg", "Bananas per kg", "produce"),
    MonitoredItem("pasta_500g", "Penne Pasta 500g", "cupboard"),
    MonitoredItem("rice_1kg", "Long Grain Rice 1kg", "cupboard"),
    MonitoredItem("baked_beans_400g", "Baked Beans 400g", "cupboard"),
    MonitoredItem("chopped_tomatoes_400g", "Chopped Tomatoes 400g", "cupboard"),
    MonitoredItem("washing_liquid_1l", "Washing Up Liquid 1L", "household"),
    MonitoredItem("toilet_rolls_9pk", "Toilet Roll 9 Pack", "household"),
    MonitoredItem("cornflakes_500g", "Cornflakes 500g", "cereal"),
    MonitoredItem("orange_juice_1l", "Orange Juice 1L Not From Concentrate", "drinks"),
]

EXTENDED_ITEMS_LIST = STAPLE_ITEMS_LIST + [
    MonitoredItem("greek_yoghurt_500g", "Greek Yoghurt 500g", "dairy"),
    MonitoredItem("natural_yoghurt_500g", "Natural Yoghurt 500g", "dairy"),
    MonitoredItem("double_cream_300ml", "Double Cream 300ml", "dairy"),
    MonitoredItem("milk_semi_2pt", "Semi Skimmed Milk 2pt", "dairy"),
    MonitoredItem("sourdough_400g", "Sourdough Loaf", "bakery"),
    MonitoredItem("rolls_6pack", "White Rolls 6 Pack", "bakery"),
    MonitoredItem("crumpets_6pack", "Crumpets 6 Pack", "bakery"),
    MonitoredItem("sausages_400g", "Pork Sausages 400g", "meat"),
    MonitoredItem("bacon_streaky_250g", "Streaky Bacon 250g", "meat"),
    MonitoredItem("salmon_fillet_2pack", "Salmon Fillets 2 Pack", "fish"),
    MonitoredItem("cod_fillet_2pack", "Cod Fillets 2 Pack", "fish"),
    MonitoredItem("carrots_1kg", "Carrots 1kg", "produce"),
    MonitoredItem("broccoli_head", "Broccoli", "produce"),
    MonitoredItem("onions_1kg", "Onions 1kg", "produce"),
    MonitoredItem("baby_spinach_200g", "Baby Spinach 200g", "produce"),
    MonitoredItem("cherry_tomatoes_250g", "Cherry Tomatoes 250g", "produce"),
    MonitoredItem("olive_oil_500ml", "Olive Oil 500ml", "cupboard"),
    MonitoredItem("sunflower_oil_1l", "Sunflower Oil 1L", "cupboard"),
    MonitoredItem("plain_flour_1_5kg", "Plain Flour 1.5kg", "cupboard"),
    MonitoredItem("sugar_1kg", "Granulated Sugar 1kg", "cupboard"),
    MonitoredItem("chicken_stock_cubes", "Chicken Stock Cubes 10 Pack", "cupboard"),
    MonitoredItem("spaghetti_500g", "Spaghetti 500g", "cupboard"),
    MonitoredItem("tuna_chunks_145g", "Tuna Chunks in Brine 145g", "cupboard"),
    MonitoredItem("cola_2l", "Cola 2L", "drinks"),
    MonitoredItem("still_water_6x500ml", "Still Water 6 x 500ml", "drinks"),
    MonitoredItem("tea_bags_80", "Tea Bags 80 Pack", "drinks"),
    MonitoredItem("instant_coffee_100g", "Instant Coffee 100g", "drinks"),
    MonitoredItem("washing_powder_1_5kg", "Washing Powder 1.5kg", "household"),
    MonitoredItem("bin_bags_50pk", "Bin Bags 50 Pack", "household"),
    MonitoredItem("kitchen_roll_2pk", "Kitchen Roll 2 Pack", "household"),
    MonitoredItem("nappies_size3_56pk", "Nappies Size 3 56 Pack", "baby"),
    MonitoredItem("shampoo_400ml", "Shampoo 400ml", "toiletries"),
    MonitoredItem("shower_gel_500ml", "Shower Gel 500ml", "toiletries"),
    MonitoredItem("frozen_peas_900g", "Frozen Peas 900g", "frozen"),
    MonitoredItem("frozen_chips_1kg", "Frozen Chips 1kg", "frozen"),
    MonitoredItem("fish_fingers_10pk", "Fish Fingers 10 Pack", "frozen"),
    MonitoredItem("crisps_6pack", "Ready Salted Crisps 6 Pack", "snacks"),
    MonitoredItem("digestive_biscuits", "Digestive Biscuits 400g", "snacks"),
]
