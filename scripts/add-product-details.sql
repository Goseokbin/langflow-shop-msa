-- Add new columns to products table
ALTER TABLE products 
ADD COLUMN IF NOT EXISTS detailed_description TEXT,
ADD COLUMN IF NOT EXISTS specifications TEXT,
ADD COLUMN IF NOT EXISTS brand VARCHAR(255),
ADD COLUMN IF NOT EXISTS rating NUMERIC(3, 2) DEFAULT 0.0,
ADD COLUMN IF NOT EXISTS review_count INTEGER DEFAULT 0;

-- Update existing products with detailed information
UPDATE products SET 
    detailed_description = CASE 
        WHEN name LIKE '%Laptop%' THEN 'Experience unparalleled performance with this cutting-edge laptop. Featuring the latest processor technology, stunning display, and all-day battery life. Perfect for professionals, students, and creative enthusiasts. Includes premium build quality with aluminum chassis and backlit keyboard.'
        WHEN name LIKE '%Phone%' OR name LIKE '%Smartphone%' THEN 'Stay connected with this flagship smartphone featuring advanced camera system, lightning-fast processor, and stunning OLED display. Capture professional-quality photos, enjoy immersive gaming, and experience seamless multitasking. Water-resistant design with premium materials.'
        WHEN name LIKE '%Headphones%' OR name LIKE '%Earbuds%' THEN 'Immerse yourself in crystal-clear audio with active noise cancellation technology. Premium drivers deliver rich bass and crisp highs. Comfortable design for all-day wear with long battery life. Perfect for music lovers, commuters, and audiophiles.'
        WHEN name LIKE '%Watch%' THEN 'Track your fitness goals and stay connected with this advanced smartwatch. Features heart rate monitoring, GPS tracking, sleep analysis, and smartphone notifications. Water-resistant design with customizable watch faces and interchangeable bands.'
        WHEN name LIKE '%Tablet%' THEN 'Versatile tablet perfect for work and entertainment. Stunning high-resolution display, powerful processor, and all-day battery life. Supports stylus input for note-taking and creative work. Lightweight and portable design.'
        WHEN name LIKE '%Camera%' THEN 'Capture stunning photos and videos with this professional-grade camera. High-resolution sensor, advanced autofocus system, and 4K video recording. Perfect for photographers and content creators. Includes image stabilization and weather-sealed body.'
        WHEN name LIKE '%Speaker%' THEN 'Fill any room with rich, immersive sound. Wireless connectivity, long battery life, and water-resistant design. Perfect for parties, outdoor adventures, or home entertainment. Premium audio quality with deep bass.'
        WHEN name LIKE '%Monitor%' THEN 'Enhance your productivity with this high-resolution monitor. Stunning color accuracy, wide viewing angles, and ergonomic design. Perfect for professionals, gamers, and content creators. Features multiple connectivity options and adjustable stand.'
        WHEN name LIKE '%Keyboard%' THEN 'Type with precision and comfort using this premium keyboard. Mechanical switches provide tactile feedback and durability. Customizable RGB lighting and programmable keys. Perfect for gamers and professionals.'
        WHEN name LIKE '%Mouse%' THEN 'Navigate with precision using this ergonomic mouse. High-DPI sensor, customizable buttons, and comfortable grip. Perfect for gaming, design work, and everyday use. Wireless connectivity with long battery life.'
        ELSE 'Premium quality product designed for modern lifestyle. Features cutting-edge technology, durable construction, and user-friendly design. Perfect for everyday use with excellent performance and reliability.'
    END,
    specifications = CASE 
        WHEN name LIKE '%Laptop%' THEN '{"Processor": "Intel Core i7 / AMD Ryzen 7", "RAM": "16GB DDR4", "Storage": "512GB SSD", "Display": "15.6 inch Full HD", "Graphics": "Integrated / Dedicated GPU", "Battery": "Up to 10 hours", "Weight": "1.8 kg", "OS": "Windows 11 / macOS"}'
        WHEN name LIKE '%Phone%' OR name LIKE '%Smartphone%' THEN '{"Display": "6.5 inch OLED", "Processor": "Snapdragon 8 Gen 2 / A16 Bionic", "RAM": "8GB", "Storage": "256GB", "Camera": "50MP Main + 12MP Ultra-wide", "Battery": "5000mAh", "5G": "Yes", "Water Resistance": "IP68"}'
        WHEN name LIKE '%Headphones%' OR name LIKE '%Earbuds%' THEN '{"Driver Size": "40mm / 10mm", "Frequency Response": "20Hz - 20kHz", "Impedance": "32 Ohms", "Battery Life": "30 hours", "Charging": "USB-C Fast Charging", "Connectivity": "Bluetooth 5.3", "ANC": "Yes", "Weight": "250g / 5g per earbud"}'
        WHEN name LIKE '%Watch%' THEN '{"Display": "1.4 inch AMOLED", "Battery Life": "Up to 7 days", "Water Resistance": "5ATM", "Sensors": "Heart Rate, GPS, Accelerometer", "Connectivity": "Bluetooth, Wi-Fi", "Compatibility": "iOS and Android", "Weight": "45g"}'
        WHEN name LIKE '%Tablet%' THEN '{"Display": "10.5 inch LCD", "Processor": "Octa-core", "RAM": "6GB", "Storage": "128GB", "Camera": "8MP Rear, 5MP Front", "Battery": "8000mAh", "OS": "Android / iPadOS", "Weight": "500g"}'
        WHEN name LIKE '%Camera%' THEN '{"Sensor": "24MP Full Frame", "ISO Range": "100-51200", "Video": "4K 60fps", "Autofocus": "693 Phase Detection Points", "Burst Mode": "10 fps", "Screen": "3.2 inch Touchscreen", "Battery": "600 shots", "Weight": "650g"}'
        WHEN name LIKE '%Speaker%' THEN '{"Power Output": "40W", "Frequency Response": "50Hz - 20kHz", "Battery Life": "12 hours", "Connectivity": "Bluetooth 5.0, AUX", "Water Resistance": "IPX7", "Dimensions": "200 x 80 x 80mm", "Weight": "900g"}'
        WHEN name LIKE '%Monitor%' THEN '{"Size": "27 inch", "Resolution": "2560 x 1440 (QHD)", "Panel Type": "IPS", "Refresh Rate": "144Hz", "Response Time": "1ms", "Brightness": "350 nits", "Ports": "HDMI, DisplayPort, USB-C", "Stand": "Height Adjustable"}'
        WHEN name LIKE '%Keyboard%' THEN '{"Switch Type": "Mechanical (Cherry MX)", "Layout": "Full Size / TKL", "Backlighting": "RGB", "Connection": "Wired / Wireless", "Polling Rate": "1000Hz", "Key Rollover": "N-Key", "Cable": "Braided USB-C"}'
        WHEN name LIKE '%Mouse%' THEN '{"DPI": "Up to 16000", "Buttons": "6 Programmable", "Sensor": "Optical", "Connection": "Wireless 2.4GHz", "Battery Life": "70 hours", "Weight": "80g", "Dimensions": "125 x 65 x 40mm"}'
        ELSE '{"Quality": "Premium", "Warranty": "1 Year", "Certification": "CE, FCC", "Package Contents": "Product, Manual, Accessories"}'
    END,
    brand = CASE 
        WHEN name LIKE '%Laptop%' THEN CASE WHEN RANDOM() < 0.5 THEN 'TechPro' ELSE 'EliteBook' END
        WHEN name LIKE '%Phone%' OR name LIKE '%Smartphone%' THEN CASE WHEN RANDOM() < 0.5 THEN 'PhoneMaster' ELSE 'SmartTech' END
        WHEN name LIKE '%Headphones%' OR name LIKE '%Earbuds%' THEN CASE WHEN RANDOM() < 0.5 THEN 'AudioMax' ELSE 'SoundWave' END
        WHEN name LIKE '%Watch%' THEN CASE WHEN RANDOM() < 0.5 THEN 'FitTime' ELSE 'SmartWear' END
        WHEN name LIKE '%Tablet%' THEN CASE WHEN RANDOM() < 0.5 THEN 'TabletPro' ELSE 'DigitalPad' END
        WHEN name LIKE '%Camera%' THEN CASE WHEN RANDOM() < 0.5 THEN 'PhotoMaster' ELSE 'VisionCam' END
        WHEN name LIKE '%Speaker%' THEN CASE WHEN RANDOM() < 0.5 THEN 'SoundBlast' ELSE 'AudioPro' END
        WHEN name LIKE '%Monitor%' THEN CASE WHEN RANDOM() < 0.5 THEN 'ViewMax' ELSE 'DisplayPro' END
        WHEN name LIKE '%Keyboard%' THEN CASE WHEN RANDOM() < 0.5 THEN 'KeyMaster' ELSE 'TypePro' END
        WHEN name LIKE '%Mouse%' THEN CASE WHEN RANDOM() < 0.5 THEN 'ClickPro' ELSE 'MouseMax' END
        ELSE 'TechBrand'
    END,
    rating = 3.5 + (RANDOM() * 1.5),  -- Random rating between 3.5 and 5.0
    review_count = FLOOR(50 + (RANDOM() * 450))::INTEGER  -- Random review count between 50 and 500
WHERE detailed_description IS NULL;

-- Made with Bob
