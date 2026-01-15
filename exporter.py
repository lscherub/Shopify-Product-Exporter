
import pandas as pd
import os

def process_product_node(product, selected_columns=None, clean_ids=True):
    """
    Flattens a product node into a list of dictionaries (one per variant).
    """
    rows = []
    
    # helper to clean ID
    def clean_id(gid):
        if not clean_ids: return gid
        if not gid: return ""
        return gid.split("/")[-1]

    # Extract product-level data
    p_id = clean_id(product.get('id', ''))
    p_title = product.get('title', '')
    p_handle = product.get('handle', '')
    p_status = product.get('status', '')
    p_vendor = product.get('vendor', '')
    p_type = product.get('productType', '')
    p_tags = ", ".join(product.get('tags', []))
    p_created = product.get('createdAt', '')
    p_updated = product.get('updatedAt', '')
    p_published = product.get('publishedAt', '')
    
    # Image count
    # mediaCount is now an object: {'count': N}
    media_count_data = product.get('mediaCount')
    if isinstance(media_count_data, dict):
        p_image_count = media_count_data.get('count', 0)
    else:
        p_image_count = media_count_data or 0
        
    # Published On (Sales Channels)
    pub_names = []
    if 'resourcePublications' in product and product['resourcePublications']:
        for edge in product['resourcePublications'].get('edges', []):
            node = edge.get('node', {})
            # Only include if actually published
            if node.get('isPublished'):
                name = node.get('publication', {}).get('name')
                if name:
                    pub_names.append(name)
    p_published_on = ", ".join(pub_names)
    
    # Variants extraction
    variants_edges = product.get('variants', {}).get('edges', [])
    p_variant_count = len(variants_edges) 
    
    if not variants_edges:
        pass 
        
    for v_edge in variants_edges:
        variant = v_edge['node']
        
        # Format options (e.g., "Size: M, Color: Red")
        options = variant.get('selectedOptions', [])
        options_str = ", ".join([f"{opt['name']}: {opt['value']}" for opt in options])
        
        # Get weight from inventoryItem
        weight_str = ""
        inv_item = variant.get('inventoryItem', {})
        if inv_item:
            measurement = inv_item.get('measurement', {})
            if measurement:
                weight_data = measurement.get('weight', {})
                w_val = weight_data.get('value', 0)
                w_unit = weight_data.get('unit', 'kg')
                weight_str = f"{w_val} {w_unit}"
        
        row = {
            'Product ID': p_id,
            'Product Title': p_title,
            'Handle': p_handle,
            'Status': p_status,
            'Vendor': p_vendor,
            'Product Type': p_type,
            'Tags': p_tags,
            'Published On': p_published_on,
            'Created At': p_created,
            'Updated At': p_updated,
            'Published At': p_published,
            'Image Count': p_image_count,
            'Variant Count': p_variant_count,
            
            'Variant ID': clean_id(variant.get('id', '')),
            'SKU': variant.get('sku', ''),
            'Barcode': variant.get('barcode', ''),
            'Price': variant.get('price', ''),
            'Compare At Price': variant.get('compareAtPrice', ''),
            'Inventory Quantity': variant.get('inventoryQuantity', 0),
            'Inventory Policy': variant.get('inventoryPolicy', ''),
            'Requires Shipping': variant.get('requiresShipping', False), # Field removed from query, defaults to False
            'Weight': weight_str,
            'Options': options_str
        }
        
        # Filter columns if selection is provided
        if selected_columns:
            # Create a new dict with only selected columns, preserving order of selection if possible or row key if not
            # Ideally we want to respect the standard order of 'row' keys but filter them.
            filtered_row = {k: row.get(k, '') for k in selected_columns if k in row}
            rows.append(filtered_row)
        else:
            rows.append(row)
        
    return rows

def save_to_excel(all_rows, filepath):
    """
    Saves the list of dictionaries to an Excel file.
    """
    if not all_rows:
        return False, "No data to save."
        
    try:
        df = pd.DataFrame(all_rows)
        # Ensure directory exists (though GUI dialog usually handles this)
        # But if filepath is just a name...
        if not filepath.endswith('.xlsx'):
            filepath += '.xlsx'
            
        df.to_excel(filepath, index=False)
        return True, f"Successfully saved to {filepath}"
    except Exception as e:
        return False, f"Export Error: {str(e)}"

def filter_duplicates(rows):
    """
    Filters the list of rows to return only those that have a duplicate SKU or Barcode.
    Empty SKUs/Barcodes are ignored.
    """
    from collections import Counter
    
    # 1. Count frequencies
    sku_counts = Counter()
    barcode_counts = Counter()
    
    for row in rows:
        sku = str(row.get('SKU', '')).strip()
        barcode = str(row.get('Barcode', '')).strip()
        
        if sku:
            sku_counts[sku] += 1
        if barcode:
            barcode_counts[barcode] += 1
            
    # 2. Identify duplicates
    duplicate_skus = {sku for sku, count in sku_counts.items() if count > 1}
    duplicate_barcodes = {bc for bc, count in barcode_counts.items() if count > 1}
    
    # 3. Filter
    result = []
    for row in rows:
        sku = str(row.get('SKU', '')).strip()
        barcode = str(row.get('Barcode', '')).strip()
        
        is_dup_sku = sku in duplicate_skus
        is_dup_barcode = barcode in duplicate_barcodes
        
        if is_dup_sku or is_dup_barcode:
            result.append(row)
            
    return result

def filter_no_images(rows):
    """
    Filters the list of rows to return only those that have an Image Count of 0.
    """
    result = []
    for row in rows:
        # Image Count should be an integer, but handle string just in case
        img_count = row.get('Image Count', 0)
        try:
            val = int(img_count)
        except ValueError:
            val = 0
            
        if val == 0:
            result.append(row)
    return result

def filter_duplicates_and_no_images(rows):
    """
    Filters rows to show DUPLICATE GROUPS where AT LEAST ONE member has No Image.
    This preserves the context (the duplicate pair) even if one has an image.
    """
    from collections import defaultdict
    
    # 1. Group by SKU and Barcode
    # A row can belong to multiple groups (if it has both SKU and Barcode), 
    # but simplest approach is to group by a primary key or check both.
    # Let's map unique_key -> [rows]. 
    # Since SKU and Barcode are independent, let's treat them as separate groups.
    # To avoid duplication in output if a row is in multiple groups, we'll collect all valid rows in a set.
    
    sku_groups = defaultdict(list)
    barcode_groups = defaultdict(list)
    
    for row in rows:
        sku = str(row.get('SKU', '')).strip()
        barcode = str(row.get('Barcode', '')).strip()
        
        if sku:
            sku_groups[sku].append(row)
        if barcode:
            barcode_groups[barcode].append(row)
            
    # 2. Identify Valid Groups
    # Valid Group: Size > 1 AND Any(row has no image)
    
    kept_rows_ids = set()
    
    def check_groups(groups):
        for key, group in groups.items():
            if len(group) < 2:
                continue
                
            has_no_image = False
            for r in group:
                try:
                    cnt = int(r.get('Image Count', 0))
                except:
                    cnt = 0
                if cnt == 0:
                    has_no_image = True
                    break
            
            if has_no_image:
                for r in group:
                    kept_rows_ids.add(id(r))
                    
    check_groups(sku_groups)
    check_groups(barcode_groups)
    
    # 3. Reconstruct list preserving order
    result = []
    for row in rows:
        if id(row) in kept_rows_ids:
            result.append(row)
            
    return result
