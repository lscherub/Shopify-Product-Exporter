
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
