require 'net/http'
require 'json'

uri = URI(ENV['CASEWORK_API_URI'] || 'http://localhost:5006')
http = Net::HTTP.new(uri.host, uri.port)

response = http.request(Net::HTTP::Delete.new('/applications'))
response = http.request(Net::HTTP::Delete.new('/registered_forms'))
response = http.request(Net::HTTP::Delete.new('/counties'))
response = http.request(Net::HTTP::Delete.new('/forms'))
response = http.request(Net::HTTP::Delete.new('/results'))

