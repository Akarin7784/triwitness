Cursor pagination issue with single page results
I was trying out the new cursor pagination 6.0.0 release and came across an issue.

page1 = shopify.Product.find(limit=100)
while page1.has_next_page():
   // do stuff

I can an error 
AttributeError: 'Collection' object has no attribute 'has_next_page'

This happens when I have less then limit results returned so there is only 1 page of results. It seems to return a Collection object instead of a PaginatedCollection.
If I reduce the limit so there will be at least 2 pages, it works fine.

For now I will use a limit I know will return multiple pages, but this means always making an extra api call.
