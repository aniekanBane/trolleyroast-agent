#!/bin/bash
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

# Results array
declare -a RESULTS

scrape_item() {
  local item_key="$1"
  local search_term="$2"
  local encoded_term=$(echo "$search_term" | sed 's/ /%20/g')
  
  # Fetch page
  local html=$(curl -s -m 10 "https://www.trolley.co.uk/search/?q=${encoded_term}" 2>/dev/null)
  
  # Extract prices per supermarket (simplified parsing)
  # Tesco
  local tesco_price=$(echo "$html" | grep -oP 'Tesco.*?£\K[0-9]+\.[0-9]{2}' | head -1)
  # ASDA
  local asda_price=$(echo "$html" | grep -oP 'ASDA.*?£\K[0-9]+\.[0-9]{2}' | head -1)
  # Sainsbury's
  local sainsburys_price=$(echo "$html" | grep -oP "Sainsbury's.*?£\K[0-9]+\.[0-9]{2}" | head -1)
  # Morrisons
  local morrisons_price=$(echo "$html" | grep -oP 'Morrisons.*?£\K[0-9]+\.[0-9]{2}' | head -1)
  # Aldi
  local aldi_price=$(echo "$html" | grep -oP 'Aldi.*?£\K[0-9]+\.[0-9]{2}' | head -1)
  # Lidl
  local lidl_price=$(echo "$html" | grep -oP 'Lidl.*?£\K[0-9]+\.[0-9]{2}' | head -1)
  
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
