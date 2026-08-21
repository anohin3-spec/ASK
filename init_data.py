"""
Скрипт для добавления тестовых данных из таблицы
"""
from database import Database

def add_initial_data():
    """Добавление начальных данных из таблицы"""
    db = Database()
    
    print("Добавление водителей...")
    # Водители
    drivers = [
        ("Мейзамидин", "+7 (999) 000-00-01"),
        ("Вова Блаженный", "+7 (999) 000-00-02"),
        ("Рамазон", "+7 (999) 000-00-03"),
        ("Вася", "+7 (999) 000-00-04"),
        ("Влад", "+7 (999) 000-00-05"),
        ("Мельников Саня", "+7 (999) 000-00-06"),
        ("Сапа/Иван", "+7 (999) 000-00-07"),
        ("Леха 1/ Сергей", "+7 (999) 000-00-08"),
        ("Женя / Леха 2", "+7 (999) 000-00-09"),
    ]
    
    driver_ids = {}
    for name, phone in drivers:
        driver_id = db.add_driver(name, phone)
        driver_ids[name] = driver_id
        print(f"  Добавлен водитель: {name}")
    
    print("\nДобавление техники...")
    # Техника
    equipment_data = [
        {
            'name': 'Case 570 ST',
            'sts_pts': '',
            'reg_number': '8613MP77',
            'measurement_type': 'mileage',
            'last_maintenance': 4500,
            'current_value': 4500,
            'interval_summer': 10000,
            'interval_winter': 7500,
            'situation': '',
            'service': '',
            'insurance_date': '29.09.2026',
            'drivers': ['Мейзамидин']
        },
        {
            'name': 'Case 570 SV',
            'sts_pts': '',
            'reg_number': '0816MO77',
            'measurement_type': 'mileage',
            'last_maintenance': 2500,
            'current_value': 2730,
            'interval_summer': 10000,
            'interval_winter': 7500,
            'situation': '',
            'service': '',
            'insurance_date': '12.11.2026',
            'drivers': ['Вова Блаженный']
        },
        {
            'name': 'Case 570 SV',
            'sts_pts': '',
            'reg_number': '2765MX77',
            'measurement_type': 'mileage',
            'last_maintenance': 4000,
            'current_value': 4177,
            'interval_summer': 10000,
            'interval_winter': 7500,
            'situation': '',
            'service': '',
            'insurance_date': '04.12.2026',
            'drivers': ['Рамазон']
        },
        {
            'name': 'Hidromek',
            'sts_pts': 'HMKH2050CP1202018',
            'reg_number': '1284MO77',
            'measurement_type': 'mileage',
            'last_maintenance': 4000,
            'current_value': 4196,
            'interval_summer': 10000,
            'interval_winter': 7500,
            'situation': '',
            'service': '',
            'insurance_date': '11.07.2026',
            'drivers': ['Вася']
        },
        {
            'name': 'Hidromek',
            'sts_pts': 'HMKH2050KR12022009',
            'reg_number': '9324мо77',
            'measurement_type': 'mileage',
            'last_maintenance': 2000,
            'current_value': 2300,
            'interval_summer': 10000,
            'interval_winter': 7500,
            'situation': '',
            'service': '',
            'insurance_date': '19.01.2027',
            'drivers': ['Влад']
        },
        {
            'name': 'Манипулятор Камаз',
            'sts_pts': '',
            'reg_number': 'A183CX797',
            'measurement_type': 'mileage',
            'last_maintenance': 22000,
            'current_value': 38885,
            'interval_summer': 10000,
            'interval_winter': 7500,
            'situation': '89771445885 Автосила',
            'service': '',
            'insurance_date': '26.12.2026',
            'drivers': ['Мельников Саня']
        },
        {
            'name': 'Самосвал Камаз',
            'sts_pts': '',
            'reg_number': 'X689CO797',
            'measurement_type': 'mileage',
            'last_maintenance': 12000,
            'current_value': 20925,
            'interval_summer': 10000,
            'interval_winter': 7500,
            'situation': '89771445885 Автосила',
            'service': '',
            'insurance_date': '',
            'drivers': ['Сапа/Иван']
        },
        {
            'name': 'FAW',
            'sts_pts': '99 72 849 548',
            'reg_number': 'O954CK797',
            'measurement_type': 'mileage',
            'last_maintenance': 26000,
            'current_value': 25000,
            'interval_summer': 10000,
            'interval_winter': 7500,
            'situation': '',
            'service': '',
            'insurance_date': '18.04.2026',
            'drivers': ['Леха 1/ Сергей']
        },
        {
            'name': 'FAW рест',
            'sts_pts': '99 73 036 141',
            'reg_number': 'B620MH977',
            'measurement_type': 'mileage',
            'last_maintenance': 15000,
            'current_value': 19454,
            'interval_summer': 10000,
            'interval_winter': 7500,
            'situation': '',
            'service': '',
            'insurance_date': '02.07.2026',
            'drivers': ['Женя / Леха 2']
        },
    ]
    
    for eq_data in equipment_data:
        drivers_list = eq_data.pop('drivers', [])
        
        eq_id = db.add_equipment(
            name=eq_data['name'],
            sts_pts=eq_data['sts_pts'],
            reg_number=eq_data['reg_number'],
            measurement_type=eq_data['measurement_type'],
            last_maintenance=eq_data['last_maintenance'],
            current_value=eq_data['current_value'],
            maintenance_interval_summer=eq_data['interval_summer'],
            maintenance_interval_winter=eq_data['interval_winter'],
            situation=eq_data['situation'],
            service=eq_data['service'],
            insurance_date=eq_data['insurance_date']
        )
        
        print(f"  Добавлена техника: {eq_data['name']} ({eq_data['reg_number']})")
        
        # Привязываем водителей
        for driver_name in drivers_list:
            if driver_name in driver_ids:
                db.assign_driver_to_equipment(eq_id, driver_ids[driver_name])
                print(f"    Привязан водитель: {driver_name}")
    
    print("\n✅ Тестовые данные успешно добавлены!")
    print("\nТеперь можно запустить программу командой: python main.py")
    
    db.close()

if __name__ == '__main__':
    try:
        add_initial_data()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("\nВозможно, данные уже были добавлены ранее.")
