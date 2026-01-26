CREATE TABLE medicines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_no VARCHAR(50) UNIQUE,
    name VARCHAR(100),
    manufacturer VARCHAR(100),
    manufacture_date DATE,
    expiry_date DATE,
    price DECIMAL(10,2),
    quantity INT
);

CREATE TABLE sales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_no VARCHAR(50),
    medicine_name VARCHAR(100),
    customer_name VARCHAR(100),
    customer_phone VARCHAR(20),
    quantity INT,
    price DECIMAL(10,2),
    total DECIMAL(10,2),
    sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);