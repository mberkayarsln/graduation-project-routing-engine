"""
Translation dictionary for the Routing Engine Web Interface.
Keys are used in templates as {{ t['key'] }}.
"""

TRANSLATIONS = {
    # Navigation & Base
    'nav_dashboard': {'en': 'Dashboard', 'tr': 'Kontrol Paneli'},
    'nav_employees': {'en': 'Employees', 'tr': 'Personeller'},
    'nav_clusters': {'en': 'Clusters', 'tr': 'Kümeler'},
    'nav_routes': {'en': 'Routes', 'tr': 'Rotalar'},
    'nav_vehicles': {'en': 'Vehicles', 'tr': 'Araçlar'},
    'nav_cost_report': {'en': 'Cost Report', 'tr': 'Maliyet Raporu'},
    'status_connected': {'en': 'Connected', 'tr': 'Bağlı'},
    'app_title': {'en': 'Routing Engine', 'tr': 'Rota Motoru'},
    'logout': {'en': 'Logout', 'tr': 'Çıkış'},

    # Dashboard
    'dashboard_title': {'en': 'Dashboard', 'tr': 'Kontrol Paneli'},
    'opt_budget': {'en': 'Budget-Friendly (fewer vehicles)', 'tr': 'Bütçe Dostu (daha az araç)'},
    'opt_balanced': {'en': 'Balanced', 'tr': 'Dengeli'},
    'opt_employee': {'en': 'Employee-Friendly (shorter walks)', 'tr': 'Çalışan Dostu (kısa yürüyüş)'},
    'btn_generate': {'en': 'Generate Routes', 'tr': 'Rotaları Oluştur'},
    'btn_refresh': {'en': 'Refresh', 'tr': 'Yenile'},
    'card_overview': {'en': 'Route Overview', 'tr': 'Rota Genel Bakış'},
    'stat_employees': {'en': 'Total Employees', 'tr': 'Toplam Personel'},
    'stat_active_emp': {'en': 'Active Employees', 'tr': 'Aktif Personel'},
    'stat_excluded_emp': {'en': 'Excluded', 'tr': 'Hariç Tutulan'},
    'stat_routes': {'en': 'Active Routes', 'tr': 'Aktif Rotalar'},
    'stat_vehicles': {'en': 'Vehicles Used', 'tr': 'Kullanılan Araç'},
    'stat_distance': {'en': 'Total Distance', 'tr': 'Toplam Mesafe'},
    'stat_duration': {'en': 'Total Duration', 'tr': 'Toplam Süre'},
    'msg_generating': {'en': 'Generating routes...', 'tr': 'Rotalar oluşturuluyor...'},
    'msg_gen_success': {'en': 'Routes generated successfully!', 'tr': 'Rotalar başarıyla oluşturuldu!'},
    'msg_gen_error': {'en': 'Error generating routes', 'tr': 'Rotalar oluşturulurken hata oluştu'},

    # Employees
    'emp_title': {'en': 'Employees', 'tr': 'Personeller'},
    'search_placeholder': {'en': 'Search employees...', 'tr': 'Personel ara...'},
    'filter_all': {'en': 'All Status', 'tr': 'Tüm Durumlar'},
    'filter_active': {'en': 'Active Only', 'tr': 'Sadece Aktif'},
    'filter_excluded': {'en': 'Excluded Only', 'tr': 'Sadece Hariç Tutulan'},
    'btn_clear': {'en': 'Clear', 'tr': 'Temizle'},
    'btn_exclude_sel': {'en': 'Exclude Selected', 'tr': 'Seçilenleri Hariç Tut'},
    'btn_include_sel': {'en': 'Include Selected', 'tr': 'Seçilenleri Dahil Et'},
    'tbl_name': {'en': 'Name', 'tr': 'Ad Soyad'},
    'tbl_location': {'en': 'Location', 'tr': 'Konum'},
    'tbl_zone': {'en': 'Zone', 'tr': 'Bölge'},
    'tbl_cluster': {'en': 'Cluster', 'tr': 'Küme'},
    'tbl_status': {'en': 'Status', 'tr': 'Durum'},
    'tbl_actions': {'en': 'Actions', 'tr': 'İşlemler'},
    'status_active': {'en': 'Active', 'tr': 'Aktif'},
    'status_excluded': {'en': 'Excluded', 'tr': 'Hariç'},
    'modal_emp_title': {'en': 'Employee Details', 'tr': 'Personel Detayları'},
    'modal_edit_title': {'en': 'Edit Employee', 'tr': 'Personel Düzenle'},
    'lbl_status': {'en': 'Status', 'tr': 'Durum'},
    'lbl_excluded_svc': {'en': 'Excluded from Service', 'tr': 'Servisten Hariç Tutuldu'},
    'lbl_reason': {'en': 'Exclusion Reason', 'tr': 'Hariç Tutma Nedeni'},
    'ph_reason': {'en': 'Enter reason...', 'tr': 'Neden giriniz...'},
    'btn_cancel': {'en': 'Cancel', 'tr': 'İptal'},
    'btn_save': {'en': 'Save Changes', 'tr': 'Değişiklikleri Kaydet'},
    'msg_loading_emp': {'en': 'Loading employees...', 'tr': 'Personeller yükleniyor...'},
    'msg_no_emp': {'en': 'No employees found', 'tr': 'Personel bulunamadı'},
    'msg_err_emp': {'en': 'Error loading employees', 'tr': 'Personeller yüklenirken hata oluştu'},

    # Vehicles
    'veh_title': {'en': 'Vehicles', 'tr': 'Araçlar'},
    'search_veh_ph': {'en': 'Search vehicles...', 'tr': 'Araç ara...'},
    'tbl_id': {'en': 'ID', 'tr': 'ID'},
    'tbl_type': {'en': 'Type', 'tr': 'Tür'},
    'tbl_driver': {'en': 'Driver', 'tr': 'Sürücü'},
    'tbl_capacity': {'en': 'Capacity', 'tr': 'Kapasite'},
    'modal_veh_title': {'en': 'Edit Vehicle', 'tr': 'Araç Düzenle'},
    'lbl_driver_name': {'en': 'Driver Name', 'tr': 'Sürücü Adı'},
    'lbl_capacity': {'en': 'Capacity', 'tr': 'Kapasite'},
    'ph_driver': {'en': 'Enter driver name', 'tr': 'Sürücü adı giriniz'},
    'msg_loading_veh': {'en': 'Loading vehicles...', 'tr': 'Araçlar yükleniyor...'},
    'msg_no_veh': {'en': 'No vehicles found', 'tr': 'Araç bulunamadı'},

    # Clusters
    'cls_title': {'en': 'Clusters', 'tr': 'Kümeler'},
    'sidebar_all_cls': {'en': 'All Clusters', 'tr': 'Tüm Kümeler'},
    'lbl_employees': {'en': 'employees', 'tr': 'personel'},
    'badge_route': {'en': 'Has Route', 'tr': 'Rota Var'},
    'badge_no_route': {'en': 'No Route', 'tr': 'Rota Yok'},
    'msg_loading_cls': {'en': 'Loading clusters...', 'tr': 'Kümeler yükleniyor...'},
    'msg_no_cls': {'en': 'No clusters found', 'tr': 'Küme bulunamadı'},

    # Routes
    'rte_title': {'en': 'Routes', 'tr': 'Rotalar'},
    'sidebar_all_rte': {'en': 'All Routes', 'tr': 'Tüm Rotalar'},
    'map_select_rte': {'en': 'Select a Route', 'tr': 'Bir Rota Seçin'},
    'dtl_distance': {'en': 'Distance', 'tr': 'Mesafe'},
    'dtl_duration': {'en': 'Duration', 'tr': 'Süre'},
    'dtl_stops': {'en': 'Stops', 'tr': 'Duraklar'},
    'dtl_bus_stops': {'en': 'Bus Stops', 'tr': 'Otobüs Durakları'},
    'dtl_employees': {'en': 'Employees', 'tr': 'Personeller'},
    'btn_details': {'en': 'Details', 'tr': 'Detaylar'},
    'btn_edit_route': {'en': 'Edit Route', 'tr': 'Rotayı Düzenle'},
    'btn_close': {'en': 'Close', 'tr': 'Kapat'},
    'btn_reset': {'en': 'Reset', 'tr': 'Sıfırla'},
    'help_drag': {'en': 'Click "Edit Route" to drag waypoints and modify the path.', 'tr': 'Ara noktaları sürükleyerek rotayı değiştirmek için "Rotayı Düzenle"ye tıklayın.'},
    'msg_loading_rte': {'en': 'Loading routes...', 'tr': 'Rotalar yükleniyor...'},
    'msg_no_rte': {'en': 'No routes found', 'tr': 'Rota bulunamadı'},
    'banner_reassign': {'en': 'Click anywhere on the map to assign {name} — or pick a highlighted stop', 'tr': '{name} için haritada herhangi bir yere tıklayın — veya vurgulanan bir durağı seçin'},
    'btn_cancel_esc': {'en': 'Cancel (Esc)', 'tr': 'İptal (Esc)'},

    # Route Edit
    'edit_title': {'en': 'Edit Route', 'tr': 'Rota Düzenle'},
    'btn_back': {'en': 'Back to Routes', 'tr': 'Rotalara Dön'},
    'panel_select': {'en': 'Select Route', 'tr': 'Rota Seçin'},
    'panel_info': {'en': 'Route Info', 'tr': 'Rota Bilgisi'},
    'panel_actions': {'en': 'Actions', 'tr': 'İşlemler'},
    'lbl_waypoints': {'en': 'Waypoints', 'tr': 'Ara Noktalar'},
    'btn_add_wp': {'en': 'Add Waypoint', 'tr': 'Ara Nokta Ekle'},
    'btn_export': {'en': 'Export JSON', 'tr': 'JSON Dışa Aktar'},
    'help_edit': {'en': 'Drag markers to edit route. Click on route line to add waypoints.', 'tr': 'Rotayı düzenlemek için işaretçileri sürükleyin. Ara nokta eklemek için rota çizgisine tıklayın.'},
    
    # Cost Report
    'card_params': {'en': 'Cost Parameters', 'tr': 'Maliyet Parametreleri'},
    'card_breakdown': {'en': 'Cost Breakdown (Monthly)', 'tr': 'Maliyet Kalemleri Detayı (Aylık)'},
    'card_contract': {'en': 'Tender Offer Summary', 'tr': 'İhale Teklif Özeti'},
    'rpt_header': {'en': 'Employee Shuttle Service — Cost Report', 'tr': 'Personel Servis Hizmeti — Maliyet Raporu'},
    'btn_calculate': {'en': 'Calculate', 'tr': 'Hesapla'},
    'btn_download_pdf': {'en': 'Download PDF', 'tr': 'PDF İndir'},
    'lbl_calculating': {'en': 'Calculating...', 'tr': 'Hesaplanıyor...'},
    'msg_calc_error': {'en': 'Error calculating report.', 'tr': 'Rapor hesaplanırken hata oluştu.'},
    'help_params': {'en': 'Edit values and click "Calculate"', 'tr': 'Değerleri düzenleyip "Hesapla" butonuna basın'},
    'rpt_date': {'en': 'Report Date', 'tr': 'Rapor Tarihi'},
    
    # Cost Report Items
    'sect_personnel': {'en': 'Personnel Expenses', 'tr': 'Personel Giderleri'},
    'sect_vehicle': {'en': 'Vehicle Expenses', 'tr': 'Araç Giderleri'},
    'sect_fuel': {'en': 'Fuel Expenses', 'tr': 'Yakıt Giderleri'},
    'sect_operation': {'en': 'Operation', 'tr': 'Operasyon'},
    'sect_tax_profit': {'en': 'Tax & Profit', 'tr': 'Vergi & Kâr'},
    'sect_total_tax': {'en': 'TOTAL & TAXES', 'tr': 'TOPLAM & VERGİLER'},
    
    'lbl_driver_salary': {'en': 'Driver Gross Salary (₺/mo)', 'tr': 'Şoför Brüt Maaş (₺/ay)'},
    'lbl_sgk': {'en': 'Social Security (Employer) (%)', 'tr': 'SGK İşveren Payı (%)'},
    'lbl_unemployment': {'en': 'Unemployment Ins. (%)', 'tr': 'İşsizlik Sigortası (%)'},
    'lbl_vehicle_rent': {'en': 'Vehicle Rent (₺/mo/vehicle)', 'tr': 'Araç Kirası (₺/ay/araç)'},
    'lbl_maintenance': {'en': 'Maintenace + Insurance (₺/mo/vehicle)', 'tr': 'Bakım + Sigorta (₺/ay/araç)'},
    'lbl_mtv': {'en': 'MTV (Motor Tax) (₺/mo/vehicle)', 'tr': 'MTV (Motorlu Taşıt Vergisi)'},
    'lbl_fuel_price': {'en': 'Fuel Price (₺/lt)', 'tr': 'Yakıt Fiyatı (₺/lt)'},
    'lbl_fuel_consumption': {'en': 'Consumption (lt/100km)', 'tr': 'Tüketim (lt/100km)'},
    'lbl_working_days': {'en': 'Monthly Working Davs', 'tr': 'Aylık İş Günü'},
    'lbl_trips': {'en': 'Daily Trips (round-trip)', 'tr': 'Günlük Sefer (gidiş-dönüş)'},
    'lbl_contract_months': {'en': 'Contract Duration (months)', 'tr': 'Sözleşme Süresi (ay)'},
    'lbl_overhead': {'en': 'Overhead (%)', 'tr': 'Genel Gider (%)'},
    'lbl_profit': {'en': 'Profit Margin (%)', 'tr': 'Kâr Marjı (%)'},
    'lbl_kdv': {'en': 'VAT (%)', 'tr': 'KDV (%)'},
    'lbl_stamp': {'en': 'Stamp Tax (%)', 'tr': 'Damga Vergisi (%)'},
    
    # Report Rows
    'row_personnel_total': {'en': 'Personnel Expenses Total', 'tr': 'Personel Giderleri Toplam'},
    'row_vehicle_total': {'en': 'Vehicle Expenses Total', 'tr': 'Araç Giderleri Toplam'},
    'row_fuel_monthly': {'en': 'Monthly Fuel Consumption', 'tr': 'Aylık Yakıt Tüketimi'},
    'row_subtotal': {'en': 'Operational Subtotal', 'tr': 'Operasyonel Ara Toplam'},
    'row_net_cost': {'en': 'Net Cost', 'tr': 'Net Maliyet'},
    'row_pre_tax': {'en': 'Total Before Tax', 'tr': 'Vergi Öncesi Toplam'},
    'row_grand_total': {'en': 'MONTHLY GRAND TOTAL (Inc. VAT)', 'tr': 'AYLIK GENEL TOPLAM (KDV DAHİL)'},
    
    'row_offer_monthly': {'en': 'Monthly Offer Price (Inc. VAT)', 'tr': 'Aylık Teklif Bedeli (KDV Dahil)'},
    'row_contract_val': {'en': 'Contract Value (Inc. VAT)', 'tr': 'Sözleşme Bedeli (KDV Dahil)'},
    'row_offer_total': {'en': 'TENDER OFFER PRICE (Total)', 'tr': 'İHALE TEKLİF FİYATI (Toplam)'},
    
    'row_cost_per_emp': {'en': 'Monthly Cost per Employee', 'tr': 'Personel Başı Aylık Maliyet'},
    'row_cost_per_veh': {'en': 'Monthly Cost per Vehicle', 'tr': 'Araç Başı Aylık Maliyet'},
    'row_cost_per_km': {'en': 'Cost per KM', 'tr': 'Kilometre Başı Maliyet'},
    
    # Missing misc keys
    'map_emp_title': {'en': 'Employee Locations', 'tr': 'Personel Konumları'},
    'route_name_fmt': {'en': 'Route {}', 'tr': 'Rota {}'},
    'start_reassign': {'en': 'Change Stop', 'tr': 'Durağı Değiştir'},
    'opt_select_ph': {'en': '-- Select a route --', 'tr': '-- Bir rota seçin --'},

    # Cost Report
    'rpt_title': {'en': 'Cost Report', 'tr': 'Maliyet Raporu'},
    'btn_calculate': {'en': 'Calculate', 'tr': 'Hesapla'},
    'btn_download_pdf': {'en': 'Download PDF', 'tr': 'PDF İndir'},
    'rpt_header': {'en': 'Personnel Service - Cost Report', 'tr': 'Personel Servis Hizmeti — Maliyet Raporu'},
    'card_params': {'en': 'Cost Parameters', 'tr': 'Maliyet Parametreleri'},
    'card_breakdown': {'en': 'Cost Breakdown (Monthly)', 'tr': 'Maliyet Kalemleri Detayı (Aylık)'},
    'card_contract': {'en': 'Contract Offer Summary', 'tr': 'İhale Teklif Özeti'},
    'sect_personnel': {'en': 'Personnel Costs', 'tr': 'Personel Giderleri'},
    'sect_vehicle': {'en': 'Vehicle Costs', 'tr': 'Araç Giderleri'},
    'sect_fuel': {'en': 'Fuel', 'tr': 'Yakıt'},
    'sect_ops': {'en': 'Operation', 'tr': 'Operasyon'},
    'sect_tax': {'en': 'Tax & Profit', 'tr': 'Vergi & Kâr'},
    'tbl_item': {'en': 'Item', 'tr': 'Kalem'},
    'tbl_unit_price': {'en': 'Unit Price', 'tr': 'Birim Tutar'},
    'tbl_qty': {'en': 'Qty', 'tr': 'Adet'},
    'tbl_total': {'en': 'Total', 'tr': 'Toplam'},
    
    # Common
    'unit_min': {'en': 'min', 'tr': 'dk'},
    'unit_km': {'en': 'km', 'tr': 'km'},
    'office': {'en': 'Office', 'tr': 'Ofis'},
    'loading': {'en': 'Loading...', 'tr': 'Yükleniyor...'},
    'calculating': {'en': 'Calculating...', 'tr': 'Hesaplanıyor...'}
}

def get_translations(lang_code='tr'):
    """Returns a dictionary of translations for the specified language."""
    # Default to Turkish if language not supported
    if lang_code not in ['en', 'tr']:
        lang_code = 'tr'
        
    return {key: val[lang_code] for key, val in TRANSLATIONS.items()}
