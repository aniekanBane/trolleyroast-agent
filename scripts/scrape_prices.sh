#!/usr/bin/env bash

# TrolleyPriceBot - Nightly Price Scraper
# Scrapes prices from Trolley.co.uk for monitored items

ITEMS=(
  "milk_semi_4pt:Semi Skimmed Milk 4pt"
  "milk_whole_4pt:Whole Milk 4pt"
  "butter_salted_250g:Salted Butter 250g"
  "bread_white_800g:White Bread 800g"
  "chicken_breast_500g:Chicken Breast 500g"
  "eggs_medium_6:Eggs Medium 6"
  "bananas_kg:Bananas"
  "apples_6pack:Apples 6 Pack"
  "potatoes_2_5kg:Potatoes 2.5kg"
  "pasta_penne_500g:Penne Pasta 500g"
)

scrape_item() {
  local item_key="$1"
  local search_term="$2"
  local encoded_term="${search_term// /%20}"
  
  # Fetch page
  local html
  html=$(curl -s -m 10 "https://www.trolley.co.uk/search/?q=${encoded_term}" 2>/dev/null)
  
  # Extract prices per supermarket (simplified parsing)
  local tesco_price asda_price sainsburys_price morrisons_price aldi_price lidl_price

  # Tesco
  tesco_price=$(echo "$html" | perl -ne 'print "$1\n" if /Tesco.*?(?:£|&pound;)(\d+\.\d{2})/' | head -1)
  # ASDA
  asda_price=$(echo "$html" | perl -ne 'print "$1\n" if /ASDA.*?(?:£|&pound;)(\d+\.\d{2})/' | head -1)
  # Sainsbury's
  sainsburys_price=$(echo "$html" | perl -ne 'print "$1\n" if /Sainsbury\x27s.*?(?:£|&pound;)(\d+\.\d{2})/' | head -1)
  # Morrisons
  morrisons_price=$(echo "$html" | perl -ne 'print "$1\n" if /Morrisons.*?(?:£|&pound;)(\d+\.\d{2})/' | head -1)
  # Aldi
  aldi_price=$(echo "$html" | perl -ne 'print "$1\n" if /Aldi.*?(?:£|&pound;)(\d+\.\d{2})/' | head -1)
  # Lidl
  lidl_price=$(echo "$html" | perl -ne 'print "$1\n" if /Lidl.*?(?:£|&pound;)(\d+\.\d{2})/' | head -1)
  
  echo "{\"item_key\":\"$item_key\",\"prices\":{\"tesco\":${tesco_price:-null},\"asda\":${asda_price:-null},\"sainsburys\":${sainsburys_price:-null},\"morrisons\":${morrisons_price:-null},\"aldi\":${aldi_price:-null},\"lidl\":${lidl_price:-null}}}"
}

echo "["
first=true
for item in "${ITEMS[@]}"; do
  IFS=':' read -r item_key search_term <<< "$item"
  
  if [ "$first" = true ]; then
    first=false
  else
    echo ","
    sleep 2  # Rate limiting
  fi
  
  scrape_item "$item_key" "$search_term"
done
echo "]"
