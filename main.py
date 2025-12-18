
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
from datetime import datetime, timedelta
from tkcalendar import DateEntry
import os

from shopify_client import ShopifyClient
from exporter import process_product_node, save_to_excel
import traceback

class ProductExporterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Shopify Product Exporter (GraphQL)")
        self.root.geometry("600x800")
        
        # Styles
        style = ttk.Style()
        style.theme_use('clam')
        
        # State variables
        self.client = None
        
        # UI Components
        self.create_auth_frame()
        self.create_filters_frame()
        self.create_action_frame()
        self.create_log_area()
        
    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def create_auth_frame(self):
        frame = ttk.LabelFrame(self.root, text="1. Authentication", padding="10")
        frame.pack(fill="x", padx=10, pady=5)
        
        # Domain
        ttk.Label(frame, text="Store Domain (e.g. mystore.myshopify.com):").grid(row=0, column=0, sticky="w")
        self.domain_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.domain_var, width=40).grid(row=0, column=1, padx=5, pady=5)
        
        # Token
        ttk.Label(frame, text="Admin API Access Token:").grid(row=1, column=0, sticky="w")
        self.token_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.token_var, width=40, show="*").grid(row=1, column=1, padx=5, pady=5)
        
        # Validate Button
        self.auth_btn = ttk.Button(frame, text="Connect & Validate", command=self.validate_auth)
        self.auth_btn.grid(row=2, column=1, sticky="e", pady=5)

    def create_filters_frame(self):
        frame = ttk.LabelFrame(self.root, text="2. Filters (Optional)", padding="10")
        frame.pack(fill="x", padx=10, pady=5)
        
        # Status
        ttk.Label(frame, text="Product Status:").grid(row=0, column=0, sticky="w")
        self.status_var = tk.StringVar(value="ANY")
        status_cb = ttk.Combobox(frame, textvariable=self.status_var, values=["ANY", "ACTIVE", "DRAFT", "ARCHIVED"], state="readonly")
        status_cb.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        # Vendor (Dynamic Dropdown)
        ttk.Label(frame, text="Vendor:").grid(row=1, column=0, sticky="w")
        self.vendor_var = tk.StringVar(value="All Vendors")
        self.vendor_cb = ttk.Combobox(frame, textvariable=self.vendor_var, state="disabled", width=38)
        self.vendor_cb['values'] = ["All Vendors"]
        self.vendor_cb.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        # Tag (Dynamic Dropdown)
        ttk.Label(frame, text="Tag:").grid(row=2, column=0, sticky="w")
        self.tag_var = tk.StringVar(value="All Tags")
        self.tag_cb = ttk.Combobox(frame, textvariable=self.tag_var, state="disabled", width=38)
        self.tag_cb['values'] = ["All Tags"]
        self.tag_cb.grid(row=2, column=1, sticky="w", padx=5, pady=2)
        
        # Date Filters
        ttk.Label(frame, text="Created After:").grid(row=3, column=0, sticky="w")
        self.date_min = DateEntry(frame, width=12, background='darkblue', foreground='white', borderwidth=2)
        self.use_date_min = tk.BooleanVar()
        tk.Checkbutton(frame, text="Enable", variable=self.use_date_min).grid(row=3, column=2, sticky="w")
        self.date_min.grid(row=3, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(frame, text="Created Before:").grid(row=4, column=0, sticky="w")
        self.date_max = DateEntry(frame, width=12, background='darkblue', foreground='white', borderwidth=2)
        self.use_date_max = tk.BooleanVar()
        tk.Checkbutton(frame, text="Enable", variable=self.use_date_max).grid(row=4, column=2, sticky="w")
        self.date_max.grid(row=4, column=1, sticky="w", padx=5, pady=2)

        # Sorting
        ttk.Label(frame, text="Sort By:").grid(row=5, column=0, sticky="w")
        self.sort_var = tk.StringVar(value="Newest First")
        sort_cb = ttk.Combobox(frame, textvariable=self.sort_var, 
                               values=["Newest First", "Oldest First", "Title A-Z", "Title Z-A"], 
                               state="readonly")
        sort_cb.grid(row=5, column=1, sticky="w", padx=5, pady=2)

    def create_action_frame(self):
        frame = ttk.LabelFrame(self.root, text="3. Export", padding="10")
        frame.pack(fill="x", padx=10, pady=5)
        
        # Limit Input
        ttk.Label(frame, text="Limit Export Amount (Empty = All):").pack(anchor="center", pady=(5,0))
        self.limit_var = tk.StringVar()
        limit_entry = ttk.Entry(frame, textvariable=self.limit_var, width=10, justify="center")
        limit_entry.pack(pady=2)
        
        self.export_btn = ttk.Button(frame, text="Fetch & Export to Excel", command=self.start_export_thread, state="disabled")
        self.export_btn.pack(pady=10)

        # Options Frame
        opts_frame = ttk.Frame(frame)
        opts_frame.pack(pady=2)
        
        # Clean IDs
        self.clean_ids_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts_frame, text="Clean IDs (remove gid://)", variable=self.clean_ids_var).pack(side="left", padx=5)

        # Column Selection
        self.selected_columns = [] # Default empty = all
        self.all_columns = [
            'Product ID', 'Product Title', 'Handle', 'Status', 'Vendor', 
            'Product Type', 'Tags', 'Created At', 'Updated At', 'Published At', 
            'Image Count', 'Variant Count', 'Variant ID', 'SKU', 'Barcode', 
            'Price', 'Compare At Price', 'Inventory Quantity', 'Inventory Policy', 
            'Requires Shipping', 'Weight', 'Options'
        ]
        ttk.Button(opts_frame, text="Select Columns", command=self.open_column_selector).pack(side="left", padx=5)

    def create_log_area(self):
        # Frame for title and toggle
        self.log_frame = ttk.LabelFrame(self.root, text="Status Log", padding="2")
        self.log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        controls = ttk.Frame(self.log_frame)
        controls.pack(fill="x")
        
        self.log_expanded = tk.BooleanVar(value=True)
        self.toggle_btn = ttk.Button(controls, text="▼", width=3, command=self.toggle_log)
        self.toggle_btn.pack(side="right", padx=2)
        
        # Container for text area to hide/show easily
        self.log_container = ttk.Frame(self.log_frame)
        self.log_container.pack(fill="both", expand=True)
        
        self.log_area = scrolledtext.ScrolledText(self.log_container, height=12, state='disabled')
        self.log_area.pack(fill="both", expand=True)

    def toggle_log(self):
        if self.log_expanded.get():
            self.log_container.pack_forget()
            self.toggle_btn.config(text="▲")
            self.log_expanded.set(False)
            # Resize window to fit if needed, or let user handle it
        else:
            self.log_container.pack(fill="both", expand=True)
            self.toggle_btn.config(text="▼")
            self.log_expanded.set(True)

    def validate_auth(self):
        domain = self.domain_var.get().strip()
        token = self.token_var.get().strip()
        
        if not domain or not token:
            messagebox.showerror("Error", "Please fill in both Domain and Token.")
            return
            
        self.log("Validating credentials...")
        self.auth_btn.config(state="disabled")
        self.client = ShopifyClient(domain, token)
        
        def run_validation():
            success, message = self.client.validate_credentials()
            if success:
                self.root.after(0, lambda: self.log(f"Success! Connected to shop: {message}"))
                self.root.after(0, lambda: self.export_btn.config(state="normal"))
                self.root.after(0, lambda: messagebox.showinfo("Success", f"Connected to {message}"))
                # Trigger vendor fetch
                self.root.after(0, self.start_vendor_fs)
                # Trigger tag fetch
                self.root.after(0, self.start_tag_fs)
            else:
                self.root.after(0, lambda: self.log(f"Main Error: {message}"))
                self.root.after(0, lambda: messagebox.showerror("Connection Failed", message))
            self.root.after(0, lambda: self.auth_btn.config(state="normal"))
                
        threading.Thread(target=run_validation, daemon=True).start()

    def start_vendor_fs(self):
        self.log("Fetching vendors list from Shopify...")
        self.vendor_cb.set("Loading...")
        
        def run():
            success, result = self.client.fetch_vendors()
            if success:
                def update_ui():
                    values = ["All Vendors"] + result
                    self.vendor_cb['values'] = values
                    self.vendor_cb.state(["!disabled"]) # enable
                    self.vendor_cb.set("All Vendors")
                    self.log(f"Vendors loaded: {len(result)}")
                self.root.after(0, update_ui)
            else:
                self.root.after(0, lambda: self.log(f"Failed to fetch vendors: {result}"))
                self.root.after(0, lambda: self.vendor_cb.set("Error loading vendors"))
                
        threading.Thread(target=run, daemon=True).start()

    def start_tag_fs(self):
        self.log("Fetching tags list from Shopify...")
        self.tag_cb.set("Loading...")
        
        def run():
            success, result = self.client.fetch_tags()
            if success:
                def update_ui():
                    values = ["All Tags"] + result
                    self.tag_cb['values'] = values
                    self.tag_cb.state(["!disabled"]) # enable
                    self.tag_cb.set("All Tags")
                    self.log(f"Tags loaded: {len(result)}")
                self.root.after(0, update_ui)
            else:
                self.root.after(0, lambda: self.log(f"Failed to fetch tags: {result}"))
                self.root.after(0, lambda: self.tag_cb.set("Error loading tags"))
                
        threading.Thread(target=run, daemon=True).start()

    def open_column_selector(self):
        top = tk.Toplevel(self.root)
        top.title("Select Columns")
        top.geometry("350x500")
        
        # Bottom frame for action button - packed first (or last with side=bottom)
        # to ensure it's always visible
        btn_frame = ttk.Frame(top, padding=10)
        btn_frame.pack(side="bottom", fill="x")
        
        # Main content
        main_frame = ttk.Frame(top)
        main_frame.pack(side="top", fill="both", expand=True, padx=10, pady=10)
        
        vars = []
        current_selection = self.selected_columns if self.selected_columns else self.all_columns
        
        cv = tk.Canvas(main_frame)
        sb = ttk.Scrollbar(main_frame, orient="vertical", command=cv.yview)
        scroll_frame = ttk.Frame(cv)
        
        scroll_frame.bind(
            "<Configure>",
            lambda e: cv.configure(scrollregion=cv.bbox("all"))
        )
        
        cv.create_window((0, 0), window=scroll_frame, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        
        # Add "Select All" / "Deselect All"
        def parse_selection():
             # Logic to update checkboxes if needed
             pass

        for col in self.all_columns:
            var = tk.BooleanVar(value=col in current_selection)
            cb = ttk.Checkbutton(scroll_frame, text=col, variable=var)
            cb.pack(anchor='w', padx=5, pady=2)
            vars.append((col, var))
            
        def apply():
            new_selection = [col for col, var in vars if var.get()]
            if len(new_selection) == len(self.all_columns) or len(new_selection) == 0:
                self.selected_columns = [] # All
            else:
                self.selected_columns = new_selection
            top.destroy()
            
        ttk.Button(btn_frame, text="Apply Selection", command=apply).pack(fill="x")

    def start_export_thread(self):
        filename = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if not filename:
            return
            
        self.export_btn.config(state="disabled")
        threading.Thread(target=self.run_export, args=(filename,), daemon=True).start()
        
    def run_export(self, filename):
        # Initialize counter strictly before try block
        exported_count = 0 
        try:
            # Map sort selection to API values
            sort_selection = self.sort_var.get()
            if sort_selection == "Newest First":
                sort_key = "CREATED_AT"
                reverse = "true"
            elif sort_selection == "Oldest First":
                sort_key = "CREATED_AT"
                reverse = "false"
            elif sort_selection == "Title A-Z":
                sort_key = "TITLE"
                reverse = "false"
            elif sort_selection == "Title Z-A":
                sort_key = "TITLE"
                reverse = "true"
            else:
                sort_key = "CREATED_AT"
                reverse = "true"

            # Limit parsing
            limit_val = self.limit_var.get().strip()
            limit = None
            if limit_val:
                if not limit_val.isdigit():
                    self.log("Warning: Invalid limit value. Exporting all products.")
                else:
                    limit = int(limit_val)
                    if limit <= 0: limit = None

            filters = {
                'status': self.status_var.get(),
                'vendor': self.vendor_var.get(),
                'tag': self.tag_var.get(),
                'sort_key': sort_key,
                'reverse': reverse
            }
            
            if self.use_date_min.get():
                filters['created_at_min'] = self.date_min.get_date().strftime("%Y-%m-%dT00:00:00Z")
            
            if self.use_date_max.get():
                filters['created_at_max'] = self.date_max.get_date().strftime("%Y-%m-%dT23:59:59Z")
                
            self.log(f"Starting export... Limit: {limit if limit else 'ALL'}")
            
            # Fetch Total Count first
            self.log("Checking total matching products...")
            success, total = self.client.fetch_product_count(filters)
            if success:
                self.log(f"Found {total} products matching your filters.")
            else:
                self.log(f"Could not fetch total count: {total}")
            
            all_rows = []
            
            # Using the generator which now supports limit and rate limiting
            for result in self.client.fetch_products(filters, limit=limit):
                if "error" in result:
                    self.log(f"Error: {result['error']}")
                    continue
                
                products = result.get("products", [])
                if not products:
                    continue
                    
                for p in products:
                    rows = process_product_node(p, self.selected_columns, clean_ids=self.clean_ids_var.get())
                    all_rows.extend(rows)
                    exported_count += 1
                
                self.log(f"Fetched {exported_count} products so far...")
                
            self.log(f"Processing finished. Total exported: {exported_count}. Saving to Excel...")
            success, msg = save_to_excel(all_rows, filename)
            
            if success:
                self.log(f"Export Complete! Saved to {filename}")
                self.root.after(0, lambda: messagebox.showinfo("Done", msg))
            else:
                self.log(f"Save failed: {msg}")
                self.root.after(0, lambda: messagebox.showerror("Error", msg))
                
        except Exception as e:
            error_trace = traceback.format_exc()
            self.log(f"Unexpected Error: {str(e)}\nTrace: {error_trace}")
            # Capture 'e' in lambda closure properly
            self.root.after(0, lambda err_msg=str(e): messagebox.showerror("Error", err_msg))
        finally:
            self.root.after(0, lambda: self.export_btn.config(state="normal"))

if __name__ == "__main__":
    root = tk.Tk()
    app = ProductExporterApp(root)
    root.mainloop()
