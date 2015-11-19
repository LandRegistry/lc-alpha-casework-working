require 'net/http'
require 'json'

uri = URI(ENV['CASEWORK_API_URI'] || 'http://localhost:5006')
http = Net::HTTP.new(uri.host, uri.port)

response = http.request(Net::HTTP::Delete.new('/workitems'))