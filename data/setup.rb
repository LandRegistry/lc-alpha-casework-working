require 'net/http'
require 'json'

uri = URI(ENV['CASEWORK_API_URI'] || 'http://localhost:5006')
http = Net::HTTP.new(uri.host, uri.port)

stock_data = '[' +
    '{"date": "2015-11-05 13:45:49", "work_type": "bank_regn", "application_type": "PA(B)", "document_id": 12},' +
    '{"date": "2015-11-05 13:45:49", "work_type": "bank_regn", "application_type": "PA(B)", "document_id": 13},' +
    '{"date": "2015-11-05 13:45:49", "work_type": "bank_regn", "application_type": "PA(B)", "document_id": 14},' +
    '{"date": "2015-11-05 13:45:50", "work_type": "bank_regn", "application_type": "PA(B)", "document_id": 15},' +
    '{"date": "2015-11-05 13:45:52", "work_type": "bank_regn", "application_type": "WO(B)", "document_id": 26},' +
    '{"date": "2015-11-05 13:45:52", "work_type": "bank_regn", "application_type": "WO(B)", "document_id": 27},' +
    '{"date": "2015-11-05 13:45:52", "work_type": "bank_regn", "application_type": "WO(B)", "document_id": 28},' +
    '{"date": "2015-11-05 13:45:52", "work_type": "bank_regn", "application_type": "WO(B)", "document_id": 29},' +
    '{"date": "2015-11-05 13:45:53", "work_type": "bank_regn", "application_type": "PA(B)", "document_id": 66},' +
    '{"date": "2015-11-05 13:45:52", "work_type": "cancel", "application_type": "WO(B)", "document_id": 31},' +
    '{"date": "2015-11-05 13:45:53", "work_type": "cancel", "application_type": "WO(B)", "document_id": 33},' +
    '{"date": "2015-11-05 13:45:53", "work_type": "cancel", "application_type": "WO(B)", "document_id": 35},' +
    '{"date": "2015-11-05 13:45:53", "work_type": "cancel", "application_type": "WO(B)", "document_id": 37},' +
    '{"date": "2015-11-05 13:45:53", "work_type": "cancel", "application_type": "WO(B)", "document_id": 39},' +
    '{"date": "2015-11-05 13:45:54", "work_type": "cancel", "application_type": "WO(B)", "document_id": 41},' +
    '{"date": "2015-11-05 13:45:54", "work_type": "amend", "application_type": "WO(B)", "document_id": 44},' +
    '{"date": "2015-11-05 13:45:54", "work_type": "amend", "application_type": "WO(B)", "document_id": 47},' +
    '{"date": "2015-11-05 13:45:55", "work_type": "amend", "application_type": "WO(B)", "document_id": 50},' +
    '{"date": "2015-11-05 13:45:55", "work_type": "amend", "application_type": "WO(B)", "document_id": 53},' +
    '{"date": "2015-11-05 13:45:56", "work_type": "amend", "application_type": "WO(B)", "document_id": 56},' +
    '{"date": "2015-11-05 13:45:56", "work_type": "amend", "application_type": "WO(B)", "document_id": 59},' +
    '{"date": "2015-11-05 13:45:56", "work_type": "search", "application_type": "Full Search", "document_id": 60},' +
    '{"date": "2015-11-05 13:45:56", "work_type": "search", "application_type": "Full Search", "document_id": 61},' +
    '{"date": "2015-11-05 13:45:56", "work_type": "search", "application_type": "Search", "document_id": 62},' +
    '{"date": "2015-11-05 13:45:56", "work_type": "search", "application_type": "Search", "document_id": 63},' +
    '{"date": "2015-11-05 13:45:56", "work_type": "search", "application_type": "Full Search", "document_id": 64},' +
    '{"date": "2015-11-05 13:45:57", "work_type": "search", "application_type": "Search", "document_id": 65}' +
']'

request = Net::HTTP::Put.new('/applications')
request.body = stock_data
request["Content-Type"] = "application/json"
response = http.request(request)
if response.code != "200"
    puts "casework-api/workitem/bulk: #{response.code}"
end


counties = counties = '[' +
    '{ "eng": "Bath and NE Somerset" },' +
    '{ "eng": "Bedford" },' +
    '{ "eng": "Blackburn with Darwen" },' +
    '{ "eng": "Blackpool" },' +
    '{ "eng": "Bournemouth" },' +
    '{ "eng": "Bracknell Forest" },' +
    '{ "eng": "Brighton & Hove" },' +
    '{ "eng": "Bristol (city of)" },' +
    '{ "eng": "Buckinghamshire" },' +
    '{ "eng": "Cambridgeshire" },' +
    '{ "eng": "Central Bedfordshire" },' +
    '{ "eng": "Cheshire East" },' +
    '{ "eng": "Cheshire West & Chester" },' +
    '{ "eng": "Cornwall (including Isles of Scilly)" },' +
    '{ "eng": "County Durham" },' +
    '{ "eng": "Cumbria" },' +
    '{ "eng": "Darlington" },' +
    '{ "eng": "Derby (city of)" },' +
    '{ "eng": "Derbyshire" },' +
    '{ "eng": "Devon" },' +
    '{ "eng": "Dorset" },' +
    '{ "eng": "East Riding of Yorkshire" },' +
    '{ "eng": "East Sussex" },' +
    '{ "eng": "Essex" },' +
    '{ "eng": "Gloucestershire" },' +
    '{ "eng": "Greater London" },' +
    '{ "eng": "Greater Manchester" },' +
    '{ "eng": "Halton" },' +
    '{ "eng": "Hampshire" },' +
    '{ "eng": "Hartlepool" },' +
    '{ "eng": "Herefordshire" },' +
    '{ "eng": "Hertfordshire" },' +
    '{ "eng": "Isle of Wight" },' +
    '{ "eng": "Kent" },' +
    '{ "eng": "Kingston upon Hull (city of)" },' +
    '{ "eng": "Lancashire" },' +
    '{ "eng": "Leicester" },' +
    '{ "eng": "Leicestershire" },' +
    '{ "eng": "Lincolnshire" },' +
    '{ "eng": "Luton" },' +
    '{ "eng": "Medway" },' +
    '{ "eng": "Merseyside" },' +
    '{ "eng": "Middlesbrough" },' +
    '{ "eng": "Milton Keynes" },' +
    '{ "eng": "Norfolk" },' +
    '{ "eng": "North East Lincolnshire" },' +
    '{ "eng": "North Somerset" },' +
    '{ "eng": "North Yorkshire" },' +
    '{ "eng": "Northamptonshire" },' +
    '{ "eng": "Northumberland" },' +
    '{ "eng": "Nottingham (city of)" },' +
    '{ "eng": "Nottinghamshire" },' +
    '{ "eng": "Oxfordshire" },' +
    '{ "eng": "Peterborough (city of)" },' +
    '{ "eng": "Plymouth (city of)" },' +
    '{ "eng": "Poole" },' +
    '{ "eng": "Portsmouth" },' +
    '{ "eng": "Reading" },' +
    '{ "eng": "Redcar and Cleveland" },' +
    '{ "eng": "Rutland" },' +
    '{ "eng": "Salop (Shropshire)" },' +
    '{ "eng": "Slough" },' +
    '{ "eng": "Somerset" },' +
    '{ "eng": "South Gloucestershire" },' +
    '{ "eng": "South Yorkshire" },' +
    '{ "eng": "Southampton" },' +
    '{ "eng": "Southend on Sea" },' +
    '{ "eng": "Staffordshire" },' +
    '{ "eng": "Stockton on Tees" },' +
    '{ "eng": "Stoke on Trent" },' +
    '{ "eng": "Suffolk" },' +
    '{ "eng": "Surrey" },' +
    '{ "eng": "Swindon" },' +
    '{ "eng": "Thurrock" },' +
    '{ "eng": "Torbay" },' +
    '{ "eng": "Tyne and Wear" },' +
    '{ "eng": "Warrington" },' +
    '{ "eng": "Warwickshire" },' +
    '{ "eng": "West Berkshire" },' +
    '{ "eng": "West Midlands" },' +
    '{ "eng": "West Sussex" },' +
    '{ "eng": "West Yorkshire" },' +
    '{ "eng": "Wiltshire" },' +
    '{ "eng": "Windsor & Maidenhead" },' +
    '{ "eng": "Wokingham" },' +
    '{ "eng": "Worcestershire" },' +
    '{ "eng": "Wrekin" },' +
    '{ "eng": "York" },' +
    '{ "eng": "Blaenau Gwent", "cym": "Blaenau Gwent" },' +
    '{ "eng": "Bridgend", "cym": "Pen-y-Bont ar Ogwr" },' +
    '{ "eng": "Caerphilly", "cym": "Caerffili" },' +
    '{ "eng": "Cardiff", "cym": "Sir Caerdydd" },' +
    '{ "eng": "Carmarthenshire", "cym": "Sir Gaerfyrddin" },' +
    '{ "eng": "Ceredigion", "cym": "Sir Ceredigion" },' +
    '{ "eng": "Conwy", "cym": "Conwy" },' +
    '{ "eng": "Denbighshire", "cym": "Sir Ddinbych" },' +
    '{ "eng": "Flintshire", "cym": "Sir y Fflint" },' +
    '{ "eng": "Gwynedd", "cym": "Gwynedd" },' +
    '{ "eng": "Isle of Anglesey", "cym": "Sir Ynys Mon" },' +
    '{ "eng": "Merthyr Tydfil", "cym": "Merthyr Tudful" },' +
    '{ "eng": "Monmouthshire", "cym": "Sir Fynwy" },' +
    '{ "eng": "Neath Port Talbot", "cym": "Castell-Nedd Port Talbot" },' +
    '{ "eng": "Newport", "cym": "Casnewydd" },' +
    '{ "eng": "Pembrokeshire", "cym": "Sir Benfro" },' +
    '{ "eng": "Powys", "cym": "Powys" },' +
    '{ "eng": "Rhondda Cynon Taff", "cym": "Rhondda Cynon Taf" },' +
    '{ "eng": "Swansea", "cym": "Sir Abertawe" },' +
    '{ "eng": "The Vale of Glamorgan", "cym": "Bro Morgannwg" },' +
    '{ "eng": "Torfaen", "cym": "Tor-Faen" },' +
    '{ "eng": "Wrexham", "cym": "Wrecsam" }' +
']'

request = Net::HTTP::Post.new('/counties')
request.body = counties
request["Content-Type"] = "application/json"
response = http.request(request)
if response.code != "200"
    puts "banks-reg/counties: #{response.code}"
end
