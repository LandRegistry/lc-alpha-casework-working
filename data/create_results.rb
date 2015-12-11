require 'net/http'
require 'json'

uri = URI(ENV['LAND_CHARGES_URI'] || 'http://localhost:5004')
http = Net::HTTP.new(uri.host, uri.port)

request = Net::HTTP::Get.new('/searches')
response = http.request(request)
data = JSON.parse(response.body)

puts data 

uri = URI(ENV['CASEWORK_API_URI'] || 'http://localhost:5006')
http = Net::HTTP.new(uri.host, uri.port)

data.each do |item|
    id = item['id']
    type = 'search nr'
    
    item['result'].each do |result|
        result.each do |key, value|
            if value.length > 0
                type = 'search'
            end
        end
    end    
    
    result = {
        "type" => type,
        "state" => "new",
        "number" => id,
    }
    request = Net::HTTP::Post.new('/results')
    request["Content-Type"] = "application/json"
    request.body = JSON.dump(result)
    response = http.request(request)
    puts response.code
end

    
regs = [    
    { 'type' => 'registration', 'state' => 'new', 'number' => '1015', 'date' => '2014-08-16' },
    { 'type' => 'registration', 'state' => 'new', 'number' => '1014', 'date' => '2014-08-16' },
    { 'type' => 'registration', 'state' => 'new', 'number' => '1013', 'date' => '2014-08-31' }
]

regs.each do |reg|
    request = Net::HTTP::Post.new('/results')
    request["Content-Type"] = "application/json"
    request.body = JSON.dump(reg)
    response = http.request(request)
    puts response.code
end