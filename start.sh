export $(cat .env | xargs) && python3 -m waystone.main
