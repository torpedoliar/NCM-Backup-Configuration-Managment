"""Credentials management view"""
import logging
from tkinter import END
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.data.repository import Repository
from app.services.crypto_service import CryptoService

logger = logging.getLogger(__name__)


class CredentialsView:
    """Credentials management view"""
    
    def __init__(self, parent, crypto_service: CryptoService):
        self.parent = parent
        self.crypto = crypto_service
        
        self.frame = ttk.Frame(parent, padding=10)
        self._create_ui()
        self._load_data()
        
        # Start auto-refresh every 60 seconds (credentials change less frequently)
        self._start_auto_refresh()
    
    def _create_ui(self):
        """Create UI components"""
        # Toolbar
        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill=X, pady=(0, 10))
        
        ttk.Button(
            toolbar,
            text="➕ Add Credential",
            command=self._add_credential,
            bootstyle=SUCCESS
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="✏️ Edit",
            command=self._edit_credential,
            bootstyle=PRIMARY
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="🗑️ Delete",
            command=self._delete_credential,
            bootstyle=DANGER
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            toolbar,
            text="🔄 Refresh",
            command=self._load_data,
            bootstyle=SECONDARY
        ).pack(side=LEFT, padx=5)
        
        # Table
        columns = ("ID", "Name", "Username", "Has Enable Password", "Created", "Updated")
        
        self.tree = ttk.Treeview(
            self.frame,
            columns=columns,
            show="headings",
            height=20
        )
        
        self.tree.column("ID", width=50, anchor=CENTER)
        self.tree.column("Name", width=200)
        self.tree.column("Username", width=200)
        self.tree.column("Has Enable Password", width=150, anchor=CENTER)
        self.tree.column("Created", width=160)
        self.tree.column("Updated", width=160)
        
        for col in columns:
            self.tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(self.frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)
    
    def _load_data(self):
        """Load credentials into table"""
        from datetime import timedelta
        
        # Store current selection
        selected_items = self.tree.selection()
        selected_id = None
        if selected_items:
            selected_id = self.tree.item(selected_items[0])['values'][0]
        
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        with Repository() as repo:
            credentials = repo.list_credentials()
            
            for cred in credentials:
                # Decrypt to check fields
                try:
                    data = self.crypto.decrypt_credential(cred.enc_blob)
                    username = data.get('username', '')
                    has_enable = "Yes" if data.get('enable_password') else "No"
                except:
                    username = "[Error]"
                    has_enable = "?"
                
                # Convert to GMT+7 timezone
                created_gmt7 = cred.created_at + timedelta(hours=7)
                updated_gmt7 = cred.updated_at + timedelta(hours=7)
                
                item_id = self.tree.insert("", END, values=(
                    cred.id,
                    cred.name,
                    username,
                    has_enable,
                    created_gmt7.strftime("%Y-%m-%d %H:%M:%S"),
                    updated_gmt7.strftime("%Y-%m-%d %H:%M:%S")
                ))
                
                # Restore selection
                if selected_id and cred.id == selected_id:
                    self.tree.selection_set(item_id)
    
    def _add_credential(self):
        """Add new credential"""
        CredentialDialog(self.frame, self.crypto, callback=self._load_data)
    
    def _edit_credential(self):
        """Edit selected credential"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a credential to edit", "No Selection")
            return
        
        cred_id = self.tree.item(selected[0])['values'][0]
        CredentialDialog(self.frame, self.crypto, cred_id=cred_id, callback=self._load_data)
    
    def _delete_credential(self):
        """Delete selected credential"""
        selected = self.tree.selection()
        if not selected:
            Messagebox.show_warning("Please select a credential to delete", "No Selection")
            return
        
        cred_name = self.tree.item(selected[0])['values'][1]
        if not Messagebox.show_question(
            f"Delete credential '{cred_name}'?",
            "Confirm Delete"
        ):
            return
        
        cred_id = self.tree.item(selected[0])['values'][0]
        
        try:
            with Repository() as repo:
                repo.delete_credential(cred_id)
            Messagebox.show_info("Credential deleted successfully", "Success")
            self._load_data()
        except ValueError as e:
            Messagebox.show_error(str(e), "Error")
        except Exception as e:
            Messagebox.show_error(f"Failed to delete credential: {e}", "Error")
    
    def _start_auto_refresh(self):
        """Start auto-refresh timer"""
        self._auto_refresh()
    
    def _auto_refresh(self):
        """Auto-refresh credentials view every 60 seconds"""
        try:
            self._load_data()
        except Exception as e:
            logger.error(f"Auto-refresh failed: {e}")
        
        # Schedule next refresh in 60 seconds
        self.frame.after(60000, self._auto_refresh)


class CredentialDialog:
    """Dialog for adding/editing credentials"""
    
    def __init__(self, parent, crypto_service, cred_id=None, callback=None):
        self.crypto = crypto_service
        self.cred_id = cred_id
        self.callback = callback
        
        self.dialog = ttk.Toplevel(parent)
        self.dialog.title("Edit Credential" if cred_id else "Add Credential")
        self.dialog.geometry("450x350")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_ui()
        
        if cred_id:
            self._load_credential_data()
    
    def _create_ui(self):
        """Create dialog UI"""
        frame = ttk.Frame(self.dialog, padding=20)
        frame.pack(fill=BOTH, expand=YES)
        
        # Name
        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky=W, pady=5)
        self.name_var = ttk.StringVar()
        ttk.Entry(frame, textvariable=self.name_var, width=35).grid(row=0, column=1, pady=5)
        
        # Username
        ttk.Label(frame, text="Username:").grid(row=1, column=0, sticky=W, pady=5)
        self.username_var = ttk.StringVar()
        ttk.Entry(frame, textvariable=self.username_var, width=35).grid(row=1, column=1, pady=5)
        
        # Password
        ttk.Label(frame, text="Password:").grid(row=2, column=0, sticky=W, pady=5)
        self.password_var = ttk.StringVar()
        ttk.Entry(frame, textvariable=self.password_var, show="*", width=35).grid(row=2, column=1, pady=5)
        
        # Enable Password
        ttk.Label(frame, text="Enable Password:").grid(row=3, column=0, sticky=W, pady=5)
        self.enable_password_var = ttk.StringVar()
        ttk.Entry(frame, textvariable=self.enable_password_var, show="*", width=35).grid(row=3, column=1, pady=5)
        ttk.Label(frame, text="(Optional)", font=("", 8), bootstyle="secondary").grid(row=4, column=1, sticky=W)
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=30)
        
        ttk.Button(btn_frame, text="Save", command=self._save, bootstyle=SUCCESS).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy, bootstyle=SECONDARY).pack(side=LEFT, padx=5)
    
    def _load_credential_data(self):
        """Load existing credential data"""
        with Repository() as repo:
            cred = repo.get_credential(self.cred_id)
            if cred:
                self.name_var.set(cred.name)
                
                # Decrypt
                try:
                    data = self.crypto.decrypt_credential(cred.enc_blob)
                    self.username_var.set(data.get('username', ''))
                    self.password_var.set(data.get('password', ''))
                    self.enable_password_var.set(data.get('enable_password', ''))
                except Exception as e:
                    Messagebox.show_error(f"Failed to decrypt credential: {e}", "Error")
    
    def _save(self):
        """Save credential"""
        name = self.name_var.get().strip()
        username = self.username_var.get().strip()
        password = self.password_var.get()
        enable_password = self.enable_password_var.get()
        
        if not name:
            Messagebox.show_error("Name is required", "Validation Error")
            return
        
        if not username:
            Messagebox.show_error("Username is required", "Validation Error")
            return
        
        if not password:
            Messagebox.show_error("Password is required", "Validation Error")
            return
        
        try:
            enc_blob = self.crypto.encrypt_credential(username, password, enable_password)
            
            with Repository() as repo:
                # Check for duplicate name (only when creating new)
                if not self.cred_id:
                    existing = repo.get_credential_by_name(name)
                    if existing:
                        Messagebox.show_error(
                            f"A credential named '{name}' already exists.\n\n"
                            f"Please choose a different name or edit the existing one.",
                            "Duplicate Name"
                        )
                        return
                
                if self.cred_id:
                    repo.update_credential(self.cred_id, name=name, enc_blob=enc_blob)
                else:
                    repo.create_credential(name, enc_blob)
            
            Messagebox.show_info("Credential saved successfully", "Success")
            self.dialog.destroy()
            
            if self.callback:
                self.callback()
        
        except Exception as e:
            # Check if it's a UNIQUE constraint error
            error_msg = str(e)
            if 'UNIQUE constraint failed' in error_msg and 'credentials.name' in error_msg:
                Messagebox.show_error(
                    f"A credential named '{name}' already exists.\n\n"
                    f"Please choose a different name or delete the existing one first.",
                    "Duplicate Credential Name"
                )
            else:
                Messagebox.show_error(f"Failed to save credential:\n\n{error_msg}", "Error")
