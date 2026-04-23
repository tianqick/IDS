CREATE DATABASE IF NOT EXISTS ids_system DEFAULT CHARSET utf8mb4;

USE ids_system;

CREATE TABLE IF NOT EXISTS user (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_info (
    id INT PRIMARY KEY AUTO_INCREMENT,
    model_name VARCHAR(100) NOT NULL,
    model_path VARCHAR(255) NOT NULL,
    model_type VARCHAR(50),
    accuracy FLOAT DEFAULT 0,
    description TEXT,
    dataset_format TEXT,
    required_columns TEXT,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dataset_info (
    id INT PRIMARY KEY AUTO_INCREMENT,
    dataset_name VARCHAR(100) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    sample_count INT DEFAULT 0,
    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS detect_record (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    source_file VARCHAR(255),
    model_id INT,
    model_name VARCHAR(100),
    model_path VARCHAR(255),
    sample_count INT DEFAULT 0,
    normal_count INT DEFAULT 0,
    attack_count INT DEFAULT 0,
    detect_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_detect_user FOREIGN KEY (user_id) REFERENCES user(id)
);

CREATE TABLE IF NOT EXISTS attack_result (
    id INT PRIMARY KEY AUTO_INCREMENT,
    record_id INT NOT NULL,
    attack_type VARCHAR(50) NOT NULL,
    risk_level VARCHAR(20) DEFAULT 'low',
    confidence FLOAT DEFAULT 0,
    src_ip VARCHAR(50),
    dst_ip VARCHAR(50),
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_attack_record FOREIGN KEY (record_id) REFERENCES detect_record(id)
);

CREATE TABLE IF NOT EXISTS alarm_log (
    id INT PRIMARY KEY AUTO_INCREMENT,
    record_id INT NOT NULL,
    alarm_content VARCHAR(255) NOT NULL,
    alarm_level VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(20) DEFAULT 'unprocessed',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alarm_record FOREIGN KEY (record_id) REFERENCES detect_record(id)
);

CREATE TABLE IF NOT EXISTS operation_log (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    detail VARCHAR(255),
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS detection_task (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    record_id INT NULL,
    model_id INT NULL,
    source_file VARCHAR(255) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    total_rows INT DEFAULT 0,
    processed_rows INT DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    message VARCHAR(255) DEFAULT 'Task queued',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_task_user FOREIGN KEY (user_id) REFERENCES user(id),
    CONSTRAINT fk_task_record FOREIGN KEY (record_id) REFERENCES detect_record(id)
);

INSERT INTO user (username, password, role)
SELECT 'admin', 'admin123', 'admin'
WHERE NOT EXISTS (SELECT 1 FROM user WHERE username = 'admin');

INSERT INTO model_info (model_name, model_path, model_type, accuracy, description, dataset_format, required_columns, is_active)
SELECT 'Hybrid IDS Model', 'best_hybrid_ids_model.pth', 'PyTorch', 96.5, 'Default demo model', 'CSV with CIC-IDS style headers.', '["Flow ID","Source IP","Destination IP","Timestamp","Label"]', TRUE
WHERE NOT EXISTS (SELECT 1 FROM model_info WHERE model_name = 'Hybrid IDS Model');
