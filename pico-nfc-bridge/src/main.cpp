/**
 * Pico NFC Bridge Firmware
 *
 * Acts as I2C slave (address 0x55) bridging ESP32 to PN5180 NFC module.
 *
 * Wiring:
 *   Pico GP19 -> PN5180 MOSI
 *   Pico GP16 -> PN5180 MISO
 *   Pico GP18 -> PN5180 SCK
 *   Pico GP17 -> PN5180 NSS
 *   Pico GP20 -> PN5180 BUSY
 *   Pico GP21 -> PN5180 RST
 *   Pico GP4  -> ESP32 I2C SDA
 *   Pico GP5  -> ESP32 I2C SCL
 */

#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>

// Pin definitions
#define PN5180_NSS   17
#define PN5180_BUSY  20
#define PN5180_RST   21
#define PN5180_MOSI  19
#define PN5180_MISO  16
#define PN5180_SCK   18

#define I2C_SDA      4
#define I2C_SCL      5
#define I2C_ADDR     0x55

// PN5180 Commands
#define PN5180_CMD_WRITE_REGISTER          0x00
#define PN5180_CMD_WRITE_REGISTER_OR_MASK  0x01
#define PN5180_CMD_WRITE_REGISTER_AND_MASK 0x02
#define PN5180_CMD_READ_REGISTER           0x04
#define PN5180_CMD_READ_EEPROM             0x07
#define PN5180_CMD_SEND_DATA               0x09
#define PN5180_CMD_READ_DATA               0x0A
#define PN5180_CMD_LOAD_RF_CONFIG          0x11
#define PN5180_CMD_RF_ON                   0x16
#define PN5180_CMD_RF_OFF                  0x17

// PN5180 Registers
#define PN5180_REG_IRQ_STATUS     0x02
#define PN5180_REG_IRQ_CLEAR      0x03
#define PN5180_REG_RX_STATUS      0x13
#define PN5180_REG_RF_STATUS      0x1D

// PN5180 EEPROM addresses
#define PN5180_EEPROM_PRODUCT_VERSION   0x10
#define PN5180_EEPROM_FIRMWARE_VERSION  0x12
#define PN5180_EEPROM_EEPROM_VERSION    0x14

// ISO15693 Commands
#define ISO15693_INVENTORY  0x01
#define ISO15693_READ_BLOCK 0x20

// I2C Command Protocol
#define CMD_GET_STATUS          0x00
#define CMD_GET_PRODUCT_VERSION 0x01
#define CMD_GET_FW_VERSION      0x02
#define CMD_GET_EEPROM_VERSION  0x03
#define CMD_RESET               0x04
#define CMD_SCAN_TAG            0x10
#define CMD_GET_UID             0x11
#define CMD_READ_BLOCK          0x20
#define CMD_WRITE_BLOCK         0x21

// Response buffer
#define RESP_BUF_SIZE 64
volatile uint8_t respBuffer[RESP_BUF_SIZE];
volatile uint8_t respLength = 0;
volatile uint8_t cmdBuffer[RESP_BUF_SIZE];
volatile uint8_t cmdLength = 0;
volatile bool cmdReady = false;

// Tag data
uint8_t tagUid[8];
bool tagPresent = false;

// Status
uint8_t lastStatus = 0; // 0=OK, 1=NO_TAG, 2=COMM_ERROR, 3=NOT_INIT

// Forward declarations
void pn5180_reset();
bool pn5180_init();
void pn5180_writeRegister(uint8_t reg, uint32_t value);
uint32_t pn5180_readRegister(uint8_t reg);
void pn5180_readEeprom(uint8_t addr, uint8_t* buffer, uint8_t len);
void pn5180_sendData(uint8_t* data, uint8_t len, uint8_t validBits);
uint8_t pn5180_readData(uint8_t* buffer, uint8_t maxLen);
void pn5180_loadRfConfig(uint8_t txConf, uint8_t rxConf);
void pn5180_rfOn();
void pn5180_rfOff();
bool pn5180_iso15693_inventory(uint8_t* uid);
bool pn5180_iso15693_readBlock(uint8_t* uid, uint8_t block, uint8_t* data);
void waitForBusyRelease();
void processCommand();

// I2C callbacks
void i2cReceive(int numBytes);
void i2cRequest();

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("Pico NFC Bridge starting...");

    // Initialize pins
    pinMode(PN5180_NSS, OUTPUT);
    pinMode(PN5180_RST, OUTPUT);
    pinMode(PN5180_BUSY, INPUT);
    digitalWrite(PN5180_NSS, HIGH);
    digitalWrite(PN5180_RST, HIGH);

    // Initialize SPI
    SPI.setRX(PN5180_MISO);
    SPI.setTX(PN5180_MOSI);
    SPI.setSCK(PN5180_SCK);
    SPI.begin();

    // Initialize PN5180
    if (pn5180_init()) {
        Serial.println("PN5180 initialized OK");
        lastStatus = 0;
    } else {
        Serial.println("PN5180 init FAILED");
        lastStatus = 3;
    }

    // Initialize I2C slave
    Wire.setSDA(I2C_SDA);
    Wire.setSCL(I2C_SCL);
    Wire.begin(I2C_ADDR);
    Wire.onReceive(i2cReceive);
    Wire.onRequest(i2cRequest);

    Serial.print("I2C slave ready at address 0x");
    Serial.println(I2C_ADDR, HEX);
}

void loop() {
    if (cmdReady) {
        processCommand();
        cmdReady = false;
    }
    delay(10);
}

void waitForBusyRelease() {
    uint32_t timeout = millis() + 100;
    while (digitalRead(PN5180_BUSY) == HIGH) {
        if (millis() > timeout) {
            Serial.println("BUSY timeout!");
            return;
        }
    }
}

void pn5180_reset() {
    digitalWrite(PN5180_RST, LOW);
    delay(10);
    digitalWrite(PN5180_RST, HIGH);
    delay(50);
    waitForBusyRelease();
}

bool pn5180_init() {
    pn5180_reset();

    // Read product version to verify communication
    uint8_t version[2];
    pn5180_readEeprom(PN5180_EEPROM_PRODUCT_VERSION, version, 2);

    Serial.print("Product version: ");
    Serial.print(version[0]);
    Serial.print(".");
    Serial.println(version[1]);

    if (version[0] == 0xFF && version[1] == 0xFF) {
        Serial.println("PN5180 not responding (got 0xFF)");
        return false;
    }
    if (version[0] == 0x00 && version[1] == 0x00) {
        Serial.println("PN5180 not responding (got 0x00)");
        return false;
    }

    // Load ISO15693 RF configuration
    pn5180_loadRfConfig(0x0D, 0x8D); // ISO15693 TX/RX config

    // Turn on RF field
    pn5180_rfOn();

    return true;
}

void pn5180_writeRegister(uint8_t reg, uint32_t value) {
    waitForBusyRelease();

    SPI.beginTransaction(SPISettings(7000000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(2);

    SPI.transfer(PN5180_CMD_WRITE_REGISTER);
    SPI.transfer(reg);
    SPI.transfer((value >> 0) & 0xFF);
    SPI.transfer((value >> 8) & 0xFF);
    SPI.transfer((value >> 16) & 0xFF);
    SPI.transfer((value >> 24) & 0xFF);

    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();

    waitForBusyRelease();
}

uint32_t pn5180_readRegister(uint8_t reg) {
    waitForBusyRelease();

    SPI.beginTransaction(SPISettings(7000000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(2);

    SPI.transfer(PN5180_CMD_READ_REGISTER);
    SPI.transfer(reg);

    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();

    waitForBusyRelease();

    // Read response
    SPI.beginTransaction(SPISettings(7000000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(2);

    uint32_t value = 0;
    value |= ((uint32_t)SPI.transfer(0xFF)) << 0;
    value |= ((uint32_t)SPI.transfer(0xFF)) << 8;
    value |= ((uint32_t)SPI.transfer(0xFF)) << 16;
    value |= ((uint32_t)SPI.transfer(0xFF)) << 24;

    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();

    return value;
}

void pn5180_readEeprom(uint8_t addr, uint8_t* buffer, uint8_t len) {
    waitForBusyRelease();

    SPI.beginTransaction(SPISettings(7000000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(2);

    SPI.transfer(PN5180_CMD_READ_EEPROM);
    SPI.transfer(addr);
    SPI.transfer(len);

    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();

    waitForBusyRelease();

    // Read response
    SPI.beginTransaction(SPISettings(7000000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(2);

    for (uint8_t i = 0; i < len; i++) {
        buffer[i] = SPI.transfer(0xFF);
    }

    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();
}

void pn5180_loadRfConfig(uint8_t txConf, uint8_t rxConf) {
    waitForBusyRelease();

    SPI.beginTransaction(SPISettings(7000000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(2);

    SPI.transfer(PN5180_CMD_LOAD_RF_CONFIG);
    SPI.transfer(txConf);
    SPI.transfer(rxConf);

    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();

    waitForBusyRelease();
}

void pn5180_rfOn() {
    waitForBusyRelease();

    SPI.beginTransaction(SPISettings(7000000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(2);

    SPI.transfer(PN5180_CMD_RF_ON);
    SPI.transfer(0x00);

    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();

    waitForBusyRelease();
}

void pn5180_rfOff() {
    waitForBusyRelease();

    SPI.beginTransaction(SPISettings(7000000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(2);

    SPI.transfer(PN5180_CMD_RF_OFF);
    SPI.transfer(0x00);

    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();

    waitForBusyRelease();
}

void pn5180_sendData(uint8_t* data, uint8_t len, uint8_t validBits) {
    // Clear IRQ status
    pn5180_writeRegister(PN5180_REG_IRQ_CLEAR, 0xFFFFFFFF);

    waitForBusyRelease();

    SPI.beginTransaction(SPISettings(7000000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(2);

    SPI.transfer(PN5180_CMD_SEND_DATA);
    SPI.transfer(validBits);
    for (uint8_t i = 0; i < len; i++) {
        SPI.transfer(data[i]);
    }

    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();

    waitForBusyRelease();
}

uint8_t pn5180_readData(uint8_t* buffer, uint8_t maxLen) {
    // Wait for RX complete
    uint32_t timeout = millis() + 100;
    while (true) {
        uint32_t irqStatus = pn5180_readRegister(PN5180_REG_IRQ_STATUS);
        if (irqStatus & 0x01) break; // RX_IRQ
        if (millis() > timeout) return 0;
    }

    // Get RX length
    uint32_t rxStatus = pn5180_readRegister(PN5180_REG_RX_STATUS);
    uint8_t rxLen = rxStatus & 0x1FF;
    if (rxLen > maxLen) rxLen = maxLen;
    if (rxLen == 0) return 0;

    waitForBusyRelease();

    SPI.beginTransaction(SPISettings(7000000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(2);

    SPI.transfer(PN5180_CMD_READ_DATA);
    SPI.transfer(0x00);

    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();

    waitForBusyRelease();

    // Read data
    SPI.beginTransaction(SPISettings(7000000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(2);

    for (uint8_t i = 0; i < rxLen; i++) {
        buffer[i] = SPI.transfer(0xFF);
    }

    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();

    return rxLen;
}

bool pn5180_iso15693_inventory(uint8_t* uid) {
    // ISO15693 Inventory command
    uint8_t cmd[] = {
        0x26,  // Flags: high data rate, 1 slot
        ISO15693_INVENTORY,
        0x00   // Mask length = 0
    };

    pn5180_sendData(cmd, sizeof(cmd), 0);

    uint8_t response[12];
    uint8_t len = pn5180_readData(response, sizeof(response));

    if (len >= 10 && response[0] == 0x00) {
        // Copy UID (bytes 2-9, reversed)
        for (int i = 0; i < 8; i++) {
            uid[i] = response[9 - i];
        }
        return true;
    }

    return false;
}

bool pn5180_iso15693_readBlock(uint8_t* uid, uint8_t block, uint8_t* data) {
    uint8_t cmd[11];
    cmd[0] = 0x22;  // Flags: high data rate, addressed
    cmd[1] = ISO15693_READ_BLOCK;
    // UID (reversed)
    for (int i = 0; i < 8; i++) {
        cmd[2 + i] = uid[7 - i];
    }
    cmd[10] = block;

    pn5180_sendData(cmd, sizeof(cmd), 0);

    uint8_t response[8];
    uint8_t len = pn5180_readData(response, sizeof(response));

    if (len >= 5 && response[0] == 0x00) {
        memcpy(data, &response[1], 4);
        return true;
    }

    return false;
}

void processCommand() {
    if (cmdLength == 0) return;

    uint8_t cmd = cmdBuffer[0];

    Serial.print("Processing command: 0x");
    Serial.println(cmd, HEX);

    switch (cmd) {
        case CMD_GET_STATUS: {
            respBuffer[0] = lastStatus;
            respBuffer[1] = tagPresent ? 1 : 0;
            respLength = 2;
            break;
        }

        case CMD_GET_PRODUCT_VERSION: {
            uint8_t version[2];
            pn5180_readEeprom(PN5180_EEPROM_PRODUCT_VERSION, version, 2);
            respBuffer[0] = 0; // OK
            respBuffer[1] = version[0];
            respBuffer[2] = version[1];
            respLength = 3;
            break;
        }

        case CMD_GET_FW_VERSION: {
            uint8_t version[2];
            pn5180_readEeprom(PN5180_EEPROM_FIRMWARE_VERSION, version, 2);
            respBuffer[0] = 0; // OK
            respBuffer[1] = version[0];
            respBuffer[2] = version[1];
            respLength = 3;
            break;
        }

        case CMD_GET_EEPROM_VERSION: {
            uint8_t version[2];
            pn5180_readEeprom(PN5180_EEPROM_EEPROM_VERSION, version, 2);
            respBuffer[0] = 0; // OK
            respBuffer[1] = version[0];
            respBuffer[2] = version[1];
            respLength = 3;
            break;
        }

        case CMD_RESET: {
            pn5180_reset();
            pn5180_init();
            respBuffer[0] = 0; // OK
            respLength = 1;
            break;
        }

        case CMD_SCAN_TAG: {
            if (pn5180_iso15693_inventory(tagUid)) {
                tagPresent = true;
                lastStatus = 0;
                respBuffer[0] = 0; // OK
                memcpy((void*)&respBuffer[1], tagUid, 8);
                respLength = 9;

                Serial.print("Tag found: ");
                for (int i = 0; i < 8; i++) {
                    Serial.print(tagUid[i], HEX);
                    Serial.print(" ");
                }
                Serial.println();
            } else {
                tagPresent = false;
                lastStatus = 1; // NO_TAG
                respBuffer[0] = 1; // NO_TAG
                respLength = 1;
            }
            break;
        }

        case CMD_GET_UID: {
            if (tagPresent) {
                respBuffer[0] = 0; // OK
                memcpy((void*)&respBuffer[1], tagUid, 8);
                respLength = 9;
            } else {
                respBuffer[0] = 1; // NO_TAG
                respLength = 1;
            }
            break;
        }

        case CMD_READ_BLOCK: {
            if (cmdLength >= 2 && tagPresent) {
                uint8_t block = cmdBuffer[1];
                uint8_t data[4];
                if (pn5180_iso15693_readBlock(tagUid, block, data)) {
                    respBuffer[0] = 0; // OK
                    memcpy((void*)&respBuffer[1], data, 4);
                    respLength = 5;
                } else {
                    respBuffer[0] = 2; // COMM_ERROR
                    respLength = 1;
                }
            } else {
                respBuffer[0] = 1; // NO_TAG
                respLength = 1;
            }
            break;
        }

        default: {
            respBuffer[0] = 0xFF; // Unknown command
            respLength = 1;
            break;
        }
    }
}

void i2cReceive(int numBytes) {
    cmdLength = 0;
    while (Wire.available() && cmdLength < RESP_BUF_SIZE) {
        cmdBuffer[cmdLength++] = Wire.read();
    }
    if (cmdLength > 0) {
        cmdReady = true;
    }
}

void i2cRequest() {
    if (respLength > 0) {
        Wire.write((uint8_t*)respBuffer, respLength);
        respLength = 0;
    } else {
        Wire.write(0xFF); // No data
    }
}
