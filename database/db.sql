CREATE DATABASE travel_system;


CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY, 
    name VARCHAR(50) NOT NULL,              
    username VARCHAR(50) UNIQUE NOT NULL,   
    password VARCHAR(255) NOT NULL,        
    birth_year INT NOT NULL,             
    birth_month INT NOT NULL,            
    birth_day INT NOT NULL,                
    phone VARCHAR(20) NOT NULL        
);


CREATE TABLE itineraries (
    id INT AUTO_INCREMENT PRIMARY KEY,                     -- 行程唯一識別碼
    itinerary_name VARCHAR(100) NOT NULL,                  -- 行程名稱
    start_time DATETIME NOT NULL,                          -- 開始時間
    end_time DATETIME NOT NULL,                            -- 結束時間
    locations TEXT NOT NULL,                               -- 地點
    latitude DOUBLE,                                       -- 新增 latitude 欄位
    longitude DOUBLE,                                      -- 新增 longitude 欄位
    description TEXT,                                      -- 描述
    price DECIMAL(10,2) NOT NULL,                          -- 價格
    photos TEXT,                                           -- 照片
    userid INT,                                            -- 使用者ID
);


CREATE TABLE messages (
    id INT AUTO_INCREMENT PRIMARY KEY,                      -- 訊息唯一識別碼
    userid INT,                                            -- 使用者ID
    receiver VARCHAR(255),                                 -- 接收者
    message TEXT,                                         -- 訊息內容
    timestamp DATETIME,                                   -- 時間戳記
    FOREIGN KEY (userid) REFERENCES users(id)             -- 參考使用者表
);

CREATE TABLE itinerary_comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    itinerary_id INT NOT NULL,
    user_id INT NOT NULL,
    comment_text TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (itinerary_id) REFERENCES itineraries(id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE user_comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL, 
    user_id INT NOT NULL, 
    comment_text TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);