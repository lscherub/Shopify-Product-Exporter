import requests
import time
import json

class ShopifyClient:
    def __init__(self, shop_domain, access_token):
        self.shop_domain = shop_domain.replace("https://", "").replace("/", "")
        self.access_token = access_token
        self.api_version = "2024-01"
        self.url = f"https://{self.shop_domain}/admin/api/{self.api_version}/graphql.json"
        
    def _get_headers(self):
        return {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.access_token
        }

    def validate_credentials(self):
        """
        Validates credentials by making a simple request to get the shop name.
        Returns (True, shop_name) if successful, (False, error_message) otherwise.
        """
        query = """
        {
          shop {
            name
          }
        }
        """
        try:
            response = requests.post(self.url, json={"query": query}, headers=self._get_headers())
            if response.status_code == 200:
                data = response.json()
                if "errors" in data:
                     return False, f"API Error: {data['errors'][0]['message']}"
                return True, data['data']['shop']['name']
            elif response.status_code == 401:
                return False, "Authentication failed. Please check your Access Token."
            else:
                return False, f"HTTP Error {response.status_code}: {response.text}"
        except Exception as e:
            return False, f"Connection Error: {str(e)}"

    def fetch_vendors(self):
        """
        Fetches all unique vendors from the shop's products.
        Returns (True, list_of_vendors) or (False, error_message).
        """
        all_vendors = set()
        cursor = None
        has_next = True
        
        # We only need the vendor field, so we query just that
        # Iterating through all products might be slow for huge stores,
        # but is the standard way if no specific vendor API exists in pure GraphQL without other apps.
        # Ideally, we utilize the 'productVendors' field on 'Shop' object if available 
        # OR just iterate products. productVendors is sometimes deprecated/restricted.
        # Let's try iterating products with a minimal query.
        
        while has_next:
            after_arg = f', after: "{cursor}"' if cursor else ""
            query = f"""
            {{
              products(first: 250{after_arg}) {{
                pageInfo {{ hasNextPage endCursor }}
                edges {{ node {{ vendor }} }}
              }}
            }}
            """
            
            try:
                # Basic rate limit sleep
                time.sleep(0.5)
                
                response = requests.post(self.url, json={"query": query}, headers=self._get_headers())
                if response.status_code != 200:
                    return False, f"HTTP {response.status_code}: {response.text}"
                
                data = response.json()
                if "errors" in data:
                    return False, f"API Error: {data['errors'][0]['message']}"
                
                products_data = data['data']['products']
                for edge in products_data['edges']:
                    v = edge['node']['vendor']
                    if v:
                         all_vendors.add(v)
                
                page_info = products_data['pageInfo']
                has_next = page_info['hasNextPage']
                cursor = page_info['endCursor']
                
            except Exception as e:
                return False, f"Fetch Vendors Exception: {str(e)}"
                
        sorted_vendors = sorted(list(all_vendors))
        return True, sorted_vendors

    def fetch_tags(self):
        """
        Fetches all unique product tags from the shop.
        Returns (True, list_of_tags) or (False, error_message).
        """
        all_tags = set()
        cursor = None
        has_next = True
        
        while has_next:
            after_arg = f'(first: 250, after: "{cursor}")' if cursor else "(first: 250)"
            query = f"""
            {{
              shop {{
                productTags{after_arg} {{
                  pageInfo {{ hasNextPage endCursor }}
                  edges {{ node }}
                }}
              }}
            }}
            """
            try:
                # Basic rate limit sleep
                time.sleep(0.5)
                
                response = requests.post(self.url, json={"query": query}, headers=self._get_headers())
                if response.status_code != 200:
                    return False, f"HTTP {response.status_code}: {response.text}"
                
                data = response.json()
                if "errors" in data:
                    return False, f"API Error: {data['errors'][0]['message']}"
                
                tags_data = data['data']['shop']['productTags']
                for edge in tags_data['edges']:
                    # edges { node } returns the tag string directly in node
                    tag = edge['node']
                    if tag:
                        all_tags.add(tag)
                
                page_info = tags_data['pageInfo']
                has_next = page_info['hasNextPage']
                cursor = page_info['endCursor']
                
            except Exception as e:
                return False, f"Fetch Tags Exception: {str(e)}"
                
        sorted_tags = sorted(list(all_tags))
        return True, sorted_tags

    def fetch_publications(self):
        """
        Fetches the list of sales channels (publications).
        Returns (True, list_of_dicts) where dict is {'id': ..., 'name': ...}
        """
        query = """
        {
          publications(first: 25) {
            edges {
              node {
                id
                name
              }
            }
          }
        }
        """
        try:
            response = requests.post(self.url, json={"query": query}, headers=self._get_headers())
            if response.status_code == 200:
                data = response.json()
                if "errors" in data:
                     return False, f"API Error: {data['errors'][0]['message']}"
                
                pubs = []
                for edge in data['data']['publications']['edges']:
                    node = edge['node']
                    pubs.append({'id': node['id'], 'name': node['name']})
                return True, pubs
            else:
                return False, f"HTTP Error {response.status_code}: {response.text}"
        except Exception as e:
            return False, f"Fetch Publications Exception: {str(e)}"

    def build_products_query(self, filters, cursor=None):
        """
        Builds the GraphQL query for fetching products based on filters.
        """
        query_parts = []
        
        if filters.get('status') and filters['status'] != 'ANY':
            query_parts.append(f"status:{filters['status']}")
        
        # Publication / Sales Channel Filter
        if filters.get('publication_id') and filters['publication_id'] != 'any':
             # The search syntax 'published_status:<publication_id>' filters for products published to that channel
             # IMPORTANT: The GID must be quoted e.g. published_status:"gid://..." OR use the numeric ID. 
             # We will use quotes around the GID.
             pub_id = filters['publication_id']
             query_parts.append(f'published_status:"{pub_id}"')

        if filters.get('vendor') and filters['vendor'] != 'All Vendors':
             # Handle possible quotes in vendor name for safety in the search syntax
             # We want the search term to be like: vendor:"My Vendor"
             # If vendor contains quotes, we need to escape them for the search parser: vendor:"My \"Best\" Vendor"
             safe_vendor = filters['vendor'].replace('"', '\\"')
             query_parts.append(f'vendor:"{safe_vendor}"')
             
        if filters.get('tag') and filters['tag'] != 'All Tags':
             safe_tag = filters['tag'].replace('"', '\\"')
             query_parts.append(f'tag:"{safe_tag}"')
            
        if filters.get('created_at_min'):
            query_parts.append(f"created_at:>={filters['created_at_min']}")
        if filters.get('created_at_max'):
            query_parts.append(f"created_at:<={filters['created_at_max']}")

        query_arg = " AND ".join(query_parts)
        
        # Use json.dumps to properly escape the string for GraphQL
        # json.dumps includes surrounding quotes, so we don't add them manually in the f-string
        query_arg_param = f', query: {json.dumps(query_arg)}' if query_arg else ""
        
        sort_key = filters.get('sort_key', 'CREATED_AT')
        reverse = str(filters.get('reverse', 'true')).lower()
        
        after_arg = f', after: "{cursor}"' if cursor else ""
        
        # We need to ask for query cost to handle rate limits
        # Note: extensions is a response key, NOT a queryable field in the schema body.
        graphql_query = f"""
        {{
          products(first: 50{after_arg}, sortKey: {sort_key}, reverse: {reverse}{query_arg_param}) {{
            pageInfo {{
              hasNextPage
              endCursor
            }}
            edges {{
              node {{
                id
                title
                handle
                status
                vendor
                productType
                tags
                createdAt
                updatedAt
                publishedAt
                totalInventory
                resourcePublications(first: 10) {{
                  edges {{
                    node {{
                      isPublished
                      publication {{
                        id
                        name
                      }}
                    }}
                  }}
                }}
                mediaCount {{ count }}
                variants(first: 50) {{
                  edges {{
                    node {{
                      id
                      sku
                      barcode
                      price
                      compareAtPrice
                      inventoryQuantity
                      inventoryPolicy
                      inventoryItem {{
                        tracked
                        measurement {{
                             weight {{ value unit }}
                        }}
                      }}
                      selectedOptions {{
                        name
                        value
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        return graphql_query

    def fetch_product_count(self, filters):
        """
        Fetches the count of products matching the filters.
        """
        query_parts = []
        if filters.get('status') and filters['status'] != 'ANY':
             query_parts.append(f"status:{filters['status']}")
        
        if filters.get('publication_id') and filters['publication_id'] != 'any':
             pub_id = filters['publication_id']
             query_parts.append(f'published_status:"{pub_id}"')

        if filters.get('vendor') and filters['vendor'] != 'All Vendors':
             safe_vendor = filters['vendor'].replace('"', '\\"')
             query_parts.append(f'vendor:"{safe_vendor}"')
             
        if filters.get('tag') and filters['tag'] != 'All Tags':
             safe_tag = filters['tag'].replace('"', '\\"')
             query_parts.append(f'tag:"{safe_tag}"')
            
        if filters.get('created_at_min'):
            query_parts.append(f"created_at:>={filters['created_at_min']}")
        if filters.get('created_at_max'):
             query_parts.append(f"created_at:<={filters['created_at_max']}")

        query_arg = " AND ".join(query_parts)
        # Use json.dumps to quote the string
        query_arg_param = f'(query: {json.dumps(query_arg)})' if query_arg else ""
        
        # productsCount query
        query = f"""
        {{
          productsCount{query_arg_param} {{
            count
          }}
        }}
        """
        
        try:
            response = requests.post(self.url, json={"query": query}, headers=self._get_headers())
            if response.status_code == 200:
                data = response.json()
                if "errors" in data:
                     return False, f"API Error: {data['errors'][0]['message']}"
                return True, data['data']['productsCount']['count']
            else:
                return False, f"HTTP Error {response.status_code}"
        except Exception as e:
            return False, f"Connection Error: {str(e)}"

    def fetch_products(self, filters, limit=None):
        """
        Generator that yields pages of products.
        Respected user-defined 'limit'.
        Handles Rate Limiting.
        """
        cursor = None
        has_next = True
        total_fetched = 0
        
        while has_next:
            # Check if we reached the user limit
            if limit is not None and total_fetched >= limit:
                break
                
            query = self.build_products_query(filters, cursor)
            
            retry_count = 0
            max_retries = 3
            backoff = 2
            
            while retry_count < max_retries:
                try:
                    response = requests.post(self.url, json={"query": query}, headers=self._get_headers())
                    
                    # Handle 429 Too Many Requests explicitly outside of 200 check if needed,
                    # but Shopify usually returns 200 with 'extensions' data unless it's a hard 429.
                    
                    if response.status_code == 429:
                        # Hard throttle
                        time.sleep(backoff)
                        backoff *= 2
                        retry_count += 1
                        continue
                        
                    if response.status_code >= 500:
                        # Server error, retry
                        time.sleep(backoff)
                        backoff *= 2
                        retry_count += 1
                        continue
                        
                    if response.status_code != 200:
                        yield {"error": f"HTTP {response.status_code}: {response.text}"}
                        return # Exit generator

                    data = response.json()
                    
                    # Check errors
                    if "errors" in data:
                        # Sometimes errors are temporary?
                        yield {"error": f"API Error: {data['errors'][0]['message']}"}
                        return

                    # Rate Limit Handling via Extensions
                    extensions = data.get('extensions', {})
                    cost = extensions.get('cost', {})
                    throttle = cost.get('throttleStatus', {})
                    currently_available = throttle.get('currentlyAvailable')
                    
                    # If we are low on credits, sleep
                    # Simple logic: if available < 100, wait a bit.
                    if currently_available is not None and currently_available < 100:
                        # Wait 2 seconds to restore some credits (50/sec usually)
                        time.sleep(2)
                    
                    products_data = data['data']['products']
                    edges = products_data['edges']
                    
                    # If we have a limit, slice the edges
                    if limit is not None:
                        remaining = limit - total_fetched
                        if len(edges) > remaining:
                            edges = edges[:remaining]
                    
                    nodes = [edge['node'] for edge in edges]
                    batch_len = len(nodes)
                    total_fetched += batch_len
                    
                    yield {"products": nodes}
                    
                    if limit is not None and total_fetched >= limit:
                        has_next = False
                        break
                    
                    # Update pagination
                    page_info = products_data['pageInfo']
                    has_next = page_info['hasNextPage']
                    cursor = page_info['endCursor']
                    
                    # Success, break retry loop
                    break
                    
                except Exception as e:
                    if retry_count == max_retries - 1:
                        yield {"error": f"Exception after retries: {str(e)}"}
                        return
                    time.sleep(backoff)
                    retry_count += 1
