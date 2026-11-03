-- ShelfWise MySQL schema (also auto-created by SQLAlchemy via seed.py;
-- this file is provided for reference / manual setup).

CREATE DATABASE IF NOT EXISTS shelfwise CHARACTER SET utf8mb4;
USE shelfwise;

CREATE TABLE IF NOT EXISTS households (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    invite_code VARCHAR(12) NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    household_id INT NULL,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(180) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'member',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    theme VARCHAR(10) DEFAULT 'dark',
    language VARCHAR(10) DEFAULT 'en',
    notify_expiry TINYINT(1) DEFAULT 1,
    notify_board TINYINT(1) DEFAULT 1,
    notify_ai_tips TINYINT(1) DEFAULT 0,
    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    household_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    category VARCHAR(30) DEFAULT 'other',
    quantity FLOAT DEFAULT 1,
    unit VARCHAR(30) DEFAULT 'unit',
    storage VARCHAR(20) DEFAULT 'fridge',
    purchase_date DATE,
    expiry_date DATE NULL,
    is_estimate TINYINT(1) DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE,
    INDEX idx_items_household (household_id)
);

CREATE TABLE IF NOT EXISTS consumption_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    quantity_used FLOAT NOT NULL,
    used_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS purchase_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    household_id INT NOT NULL,
    item_name VARCHAR(150) NOT NULL,
    category VARCHAR(30) DEFAULT 'other',
    purchase_date DATE,
    quantity FLOAT DEFAULT 1,
    unit VARCHAR(30) DEFAULT 'unit',
    was_wasted TINYINT(1) DEFAULT 0,
    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE,
    INDEX idx_purchase_household (household_id)
);

CREATE TABLE IF NOT EXISTS shopping_list (
    id INT AUTO_INCREMENT PRIMARY KEY,
    household_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    added_by_id INT NULL,
    is_purchased TINYINT(1) DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE,
    FOREIGN KEY (added_by_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS board_notes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    household_id INT NOT NULL,
    text VARCHAR(150) NOT NULL,
    color VARCHAR(20) DEFAULT 'yellow',
    posted_by_id INT NOT NULL,
    is_bought TINYINT(1) DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE,
    FOREIGN KEY (posted_by_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    household_id INT NOT NULL,
    user_id INT NOT NULL,
    role VARCHAR(10) NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Multi-household support ---------------------------------------------------
-- users.household_id is the household the user is *currently working in*.
CREATE TABLE IF NOT EXISTS household_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    household_id INT NOT NULL,
    role VARCHAR(20) DEFAULT 'member',
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_member_user_household (user_id, household_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS invites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    household_id INT NOT NULL,
    invited_by_id INT NULL,
    email VARCHAR(180) NULL,
    token VARCHAR(64) NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    accepted_by_id INT NULL,
    accepted_at DATETIME NULL,
    revoked TINYINT(1) DEFAULT 0,
    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE,
    FOREIGN KEY (invited_by_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (accepted_by_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Existing installs: give current users a membership for their current household
INSERT IGNORE INTO household_members (user_id, household_id, role)
SELECT id, household_id, COALESCE(role, 'member') FROM users WHERE household_id IS NOT NULL;
