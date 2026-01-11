/**
 * Pico NFC Bridge - Manual PN5180 driver
 * I2C slave (0x55) bridging ESP32 to PN5180
 */

#include <SPI.h>
#include <Wire.h>

#define PN5180_NSS   17
#define PN5180_BUSY  20
#define PN5180_RST   21

#define I2C_SDA      4
#define I2C_SCL      5
#define I2C_ADDR     0x55

#define CMD_GET_STATUS          0x00
#define CMD_GET_PRODUCT_VERSION 0x01
#define CMD_SCAN_TAG            0x10

volatile uint8_t respBuffer[64];
volatile uint8_t respLength = 0;
volatile uint8_t cmdBuffer[64];
volatile uint8_t cmdLength = 0;
volatile bool cmdReady = false;

uint8_t tagUid[10];
uint8_t tagUidLen = 0;
bool tagPresent = false;
uint8_t lastStatus = 0;
uint8_t cachedVersion[2] = {0xFF, 0xFF};
uint8_t consecutiveFailures = 0;
const uint8_t MAX_FAILURES_BEFORE_RESET = 3;
uint32_t lastResetTime = 0;
const uint32_t RESET_COOLDOWN_MS = 500;  // Wait 500ms after reset before scanning

void waitBusy() {
    uint32_t start = millis();
    // Wait for BUSY to go HIGH first (command processing)
    while (digitalRead(PN5180_BUSY) == LOW) {
        if (millis() - start > 10) break;
    }
    // Then wait for BUSY to go LOW (command complete)
    while (digitalRead(PN5180_BUSY) == HIGH) {
        if (millis() - start > 100) return;
    }
}

// Read data from PN5180 RX buffer using 2-frame approach per datasheet
void pn5180_readData(uint8_t* buf, uint8_t len) {
    // Frame 1: Send READ_DATA command (0x0A, 0x00)
    SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(2);
    SPI.transfer(0x0A);  // READ_DATA command
    SPI.transfer(0x00);  // Required second byte
    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();

    // Wait for BUSY sequence
    waitBusy();

    // Frame 2: Read the data
    SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(2);
    for (uint8_t i = 0; i < len; i++) {
        buf[i] = SPI.transfer(0xFF);
    }
    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();
}

void pn5180_readEeprom(uint8_t addr, uint8_t* buf, uint8_t len) {
    SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(5);
    SPI.transfer(0x07);
    SPI.transfer(addr);
    SPI.transfer(len);
    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();

    delayMicroseconds(100);
    waitBusy();
    delayMicroseconds(100);

    SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(5);
    for (uint8_t i = 0; i < len; i++) {
        buf[i] = SPI.transfer(0xFF);
    }
    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();
}

void pn5180_writeRegister(uint8_t reg, uint32_t value) {
    SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(5);
    SPI.transfer(0x00);
    SPI.transfer(reg);
    SPI.transfer(value & 0xFF);
    SPI.transfer((value >> 8) & 0xFF);
    SPI.transfer((value >> 16) & 0xFF);
    SPI.transfer((value >> 24) & 0xFF);
    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();
    delayMicroseconds(100);
    waitBusy();
}

void pn5180_writeRegisterAndMask(uint8_t reg, uint32_t mask) {
    SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(5);
    SPI.transfer(0x02);  // WRITE_REGISTER_AND_MASK
    SPI.transfer(reg);
    SPI.transfer(mask & 0xFF);
    SPI.transfer((mask >> 8) & 0xFF);
    SPI.transfer((mask >> 16) & 0xFF);
    SPI.transfer((mask >> 24) & 0xFF);
    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();
    delayMicroseconds(100);
    waitBusy();
}

uint32_t pn5180_readRegister(uint8_t reg) {
    SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(5);
    SPI.transfer(0x04);
    SPI.transfer(reg);
    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();

    delayMicroseconds(100);
    waitBusy();
    delayMicroseconds(100);

    SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(5);
    uint32_t val = SPI.transfer(0xFF);
    val |= ((uint32_t)SPI.transfer(0xFF)) << 8;
    val |= ((uint32_t)SPI.transfer(0xFF)) << 16;
    val |= ((uint32_t)SPI.transfer(0xFF)) << 24;
    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();
    return val;
}

void pn5180_loadRfConfig(uint8_t tx, uint8_t rx) {
    pn5180_writeRegister(0x03, 0xFFFFFFFF);  // Clear IRQ
    delayMicroseconds(100);

    SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(5);
    SPI.transfer(0x11);  // LOAD_RF_CONFIG
    SPI.transfer(tx);
    SPI.transfer(rx);
    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();
    delayMicroseconds(100);
    waitBusy();
    delay(10);
}

void pn5180_rfOn() {
    SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(5);
    SPI.transfer(0x16);  // RF_ON
    SPI.transfer(0x00);
    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();
    delayMicroseconds(100);
    waitBusy();
    delay(10);
}

// ISO14443A activation
// Returns: 0 = no tag, 4/7/10 = UID length, 0xFF = chip stuck (needs hard reset)
uint8_t activateTypeA(uint8_t *uid) {
    // Turn OFF Crypto (SYSTEM_CONFIG = 0x00)
    pn5180_writeRegisterAndMask(0x00, 0xFFFFFFBF);
    // Clear RX CRC (CRC_RX_CONFIG = 0x12)
    pn5180_writeRegisterAndMask(0x12, 0xFFFFFFFE);
    // Clear TX CRC (CRC_TX_CONFIG = 0x19)
    pn5180_writeRegisterAndMask(0x19, 0xFFFFFFFE);

    // Clear IRQ status
    pn5180_writeRegister(0x03, 0xFFFFFFFF);

    // Reset transceive state by going to idle first
    uint32_t sysConfig = pn5180_readRegister(0x00);
    pn5180_writeRegister(0x00, sysConfig & 0xFFFFFFF8);  // Set to Idle
    delay(1);
    pn5180_writeRegister(0x00, (sysConfig & 0xFFFFFFF8) | 0x03);  // Set to Transceive
    delay(2);

    SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(5);
    SPI.transfer(0x09);  // SEND_DATA
    SPI.transfer(0x07);  // 7 valid bits
    SPI.transfer(0x52);  // WUPA
    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();
    delayMicroseconds(100);
    waitBusy();
    delay(5);

    // Check RX status
    uint32_t rxStatus = pn5180_readRegister(0x13);
    uint16_t rxLen = rxStatus & 0x1FF;

    // Debug: show rxLen
    if (rxLen != 0 && rxLen != 2) {
        Serial.print("WUPA rxLen=");
        Serial.println(rxLen);
    }

    // Detect stuck state: rxLen=511 (0x1FF) means all bits set = garbage
    if (rxLen == 511) {
        Serial.println("STUCK: rxLen=511");
        return 0xFF;  // Signal chip is stuck
    }

    if (rxLen < 2) {
        // Try REQA
        pn5180_writeRegister(0x03, 0xFFFFFFFF);
        delay(2);

        SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
        digitalWrite(PN5180_NSS, LOW);
        delayMicroseconds(5);
        SPI.transfer(0x09);
        SPI.transfer(0x07);
        SPI.transfer(0x26);  // REQA
        digitalWrite(PN5180_NSS, HIGH);
        SPI.endTransaction();
        delayMicroseconds(100);
        waitBusy();
        delay(5);

        rxStatus = pn5180_readRegister(0x13);
        rxLen = rxStatus & 0x1FF;

        // Debug
        if (rxLen != 0 && rxLen != 2) {
            Serial.print("REQA rxLen=");
            Serial.println(rxLen);
        }

        // Detect stuck state again
        if (rxLen == 511) {
            Serial.println("STUCK: rxLen=511 after REQA");
            return 0xFF;
        }

        if (rxLen < 2) return 0;
    }

    // Read ATQA using 2-phase read
    uint8_t atqa[2];
    pn5180_readData(atqa, 2);

    // Detect stuck state: ATQA=0xFF,0xFF is garbage
    if (atqa[0] == 0xFF && atqa[1] == 0xFF) {
        Serial.println("STUCK: ATQA=FF,FF");
        return 0xFF;
    }

    if (atqa[0] == 0xFF || atqa[0] == 0x00) return 0;

    // Anti-collision Level 1 - need to reset transceive mode
    pn5180_writeRegister(0x03, 0xFFFFFFFF);  // Clear IRQ

    // Reset to transceive mode
    sysConfig = pn5180_readRegister(0x00);
    sysConfig = (sysConfig & 0xFFFFFFF8) | 0x03;
    pn5180_writeRegister(0x00, sysConfig);
    delay(2);

    SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(5);
    SPI.transfer(0x09);  // SEND_DATA
    SPI.transfer(0x00);  // 8 bits (full bytes)
    SPI.transfer(0x93);  // Anticollision CL1
    SPI.transfer(0x20);  // NVB = 0x20
    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();
    delayMicroseconds(100);
    waitBusy();
    delay(10);

    rxStatus = pn5180_readRegister(0x13);
    rxLen = rxStatus & 0x1FF;

    if (rxLen < 5 || rxLen > 64) return 0;

    // Read UID (5 bytes: 4 UID + 1 BCC)
    uint8_t uidBuf[5];
    pn5180_readData(uidBuf, 5);
    memcpy(uid, uidBuf, 4);

    // Verify BCC (XOR of all UID bytes)
    uint8_t bcc = uid[0] ^ uid[1] ^ uid[2] ^ uid[3];
    if (bcc != uidBuf[4]) return 0;

    return 4;  // 4-byte UID
}

void pn5180_setTransceiveMode() {
    // Read current SYSTEM_CONFIG
    uint32_t sysConfig = pn5180_readRegister(0x00);
    // Clear command bits (0-2) and set to Transceive (3)
    sysConfig = (sysConfig & 0xFFFFFFF8) | 0x03;
    pn5180_writeRegister(0x00, sysConfig);
}

void pn5180_rfOff() {
    SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
    digitalWrite(PN5180_NSS, LOW);
    delayMicroseconds(5);
    SPI.transfer(0x17);  // RF_OFF
    SPI.transfer(0x00);
    digitalWrite(PN5180_NSS, HIGH);
    SPI.endTransaction();
    delayMicroseconds(100);
    waitBusy();
    delay(5);
}

// Hard reset the PN5180 via RST pin - use when chip gets stuck
void pn5180_hardReset() {
    Serial.println("*** HARD RESET ***");

    // Pull RST low for longer
    digitalWrite(PN5180_RST, LOW);
    delay(50);
    digitalWrite(PN5180_RST, HIGH);
    delay(100);
    waitBusy();
    delay(50);

    // Re-initialize RF
    pn5180_loadRfConfig(0x00, 0x80);  // ISO14443A 106kbps
    delay(20);
    pn5180_rfOn();
    delay(50);

    consecutiveFailures = 0;
    lastResetTime = millis();
    Serial.println("Reset complete - cooling down");
}

bool scanTag() {
    static uint8_t noTagCount = 0;

    // If we haven't seen a tag for a while, do a full hardware reset
    if (noTagCount > 3) {
        Serial.println("No tag for 3 scans - HARD RESET");
        pn5180_hardReset();
        noTagCount = 0;
        return false;  // Skip this scan, let cooldown happen
    }

    // Turn RF off then on to reset field
    pn5180_rfOff();
    delay(20);

    pn5180_writeRegister(0x03, 0xFFFFFFFF);  // Clear all IRQ
    delay(5);
    pn5180_loadRfConfig(0x00, 0x80);  // ISO14443A 106kbps
    delay(10);
    pn5180_rfOn();
    delay(30);  // Wait for RF field to stabilize
    pn5180_setTransceiveMode();

    uint8_t uid[10];
    uint8_t uidLen = activateTypeA(uid);

    // Check for stuck state (0xFF return)
    if (uidLen == 0xFF) {
        consecutiveFailures++;
        noTagCount++;
        if (consecutiveFailures >= MAX_FAILURES_BEFORE_RESET) {
            pn5180_hardReset();
            noTagCount = 0;
        }
        tagPresent = false;
        return false;
    }

    if (uidLen > 0 && uidLen <= 10) {
        consecutiveFailures = 0;  // Reset counter on success
        noTagCount = 0;
        tagUidLen = uidLen;
        memcpy(tagUid, uid, uidLen);
        tagPresent = true;
        return true;
    }

    // Normal "no tag" - increment counter for recovery logic
    noTagCount++;
    tagPresent = false;
    return false;
}

void processCommand() {
    if (cmdLength == 0) return;
    uint8_t cmd = cmdBuffer[0];

    Serial.print("CMD: 0x");
    Serial.println(cmd, HEX);

    switch (cmd) {
        case CMD_GET_STATUS:
            respBuffer[0] = lastStatus;
            respBuffer[1] = tagPresent ? 1 : 0;
            respLength = 2;
            break;

        case CMD_GET_PRODUCT_VERSION:
            respBuffer[0] = 0;
            respBuffer[1] = cachedVersion[0];
            respBuffer[2] = cachedVersion[1];
            respLength = 3;
            break;

        case CMD_SCAN_TAG:
            if (scanTag()) {
                respBuffer[0] = 0;
                respBuffer[1] = tagUidLen;
                memcpy((void*)&respBuffer[2], tagUid, tagUidLen);
                respLength = 2 + tagUidLen;
            } else {
                respBuffer[0] = 1;
                respLength = 1;
            }
            break;

        default:
            respBuffer[0] = 0xFF;
            respLength = 1;
    }
}

void i2cReceive(int n) {
    Serial.print("I2C RX: ");
    Serial.print(n);
    Serial.print(" bytes: ");
    cmdLength = 0;
    while (Wire.available() && cmdLength < 64) {
        cmdBuffer[cmdLength++] = Wire.read();
    }
    for (int i = 0; i < cmdLength; i++) {
        Serial.print(cmdBuffer[i], HEX);
        Serial.print(" ");
    }
    Serial.println();
    cmdReady = true;
}

void i2cRequest() {
    Serial.print("I2C REQ: ");
    if (respLength > 0) {
        Serial.print(respLength);
        Serial.println(" bytes");
        Wire.write((uint8_t*)respBuffer, respLength);
        respLength = 0;
    } else {
        Serial.println("no data, sending 0xFF");
        Wire.write(0xFF);
    }
}

void setup() {
    pinMode(LED_BUILTIN, OUTPUT);
    Serial.begin(115200);
    delay(2000);
    Serial.println("Pico NFC Bridge starting...");

    pinMode(PN5180_NSS, OUTPUT);
    digitalWrite(PN5180_NSS, HIGH);
    pinMode(PN5180_RST, OUTPUT);
    digitalWrite(PN5180_RST, HIGH);
    pinMode(PN5180_BUSY, INPUT);

    SPI.setRX(16);
    SPI.setTX(19);
    SPI.setSCK(18);
    SPI.begin();
    Serial.println("SPI OK");

    // Reset PN5180
    digitalWrite(PN5180_RST, LOW);
    delay(10);
    digitalWrite(PN5180_RST, HIGH);
    delay(50);
    waitBusy();
    Serial.println("Reset OK");

    // Read version
    pn5180_readEeprom(0x10, cachedVersion, 2);
    Serial.print("PN5180 version: ");
    Serial.print(cachedVersion[0]);
    Serial.print(".");
    Serial.println(cachedVersion[1]);

    if (cachedVersion[0] == 0xFF && cachedVersion[1] == 0xFF) {
        Serial.println("PN5180 ERROR!");
        lastStatus = 3;
    } else {
        pn5180_loadRfConfig(0x00, 0x80);  // ISO14443A
        pn5180_rfOn();
        Serial.println("RF ON (ISO14443A)");
        lastStatus = 0;
        // Skip test scan - go straight to main loop
    }

    Wire.setSDA(I2C_SDA);
    Wire.setSCL(I2C_SCL);
    Wire.begin(I2C_ADDR);
    Wire.onReceive(i2cReceive);
    Wire.onRequest(i2cRequest);
    Serial.println("I2C ready at 0x55");
    Serial.println("Ready!");
}

void loop() {
    static uint32_t lastBlink = 0;
    static uint32_t lastScan = 0;
    static uint32_t lastI2cStatus = 0;

    if (millis() - lastBlink > 500) {
        lastBlink = millis();
        digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    }

    // Debug: show I2C status every 5 seconds
    if (millis() - lastI2cStatus > 5000) {
        lastI2cStatus = millis();
        Serial.print("I2C slave @ 0x");
        Serial.print(I2C_ADDR, HEX);
        Serial.print(" on GP");
        Serial.print(I2C_SDA);
        Serial.print("/GP");
        Serial.println(I2C_SCL);
    }

    // Periodic tag scan every 1 second (but respect reset cooldown)
    if (millis() - lastScan > 1000) {
        lastScan = millis();

        // Skip scanning if we just did a hard reset
        if (millis() - lastResetTime >= RESET_COOLDOWN_MS) {
            bool found = scanTag();
            if (found) {
                Serial.print("TAG: ");
                for (int i = 0; i < tagUidLen; i++) {
                    if (tagUid[i] < 0x10) Serial.print("0");
                    Serial.print(tagUid[i], HEX);
                }
                Serial.println();
            } else if (!tagPresent) {
                Serial.println(".");  // Show we're still scanning
            }
        } else {
            Serial.println("(cooldown)");
        }
    }

    if (cmdReady) {
        processCommand();
        cmdReady = false;
    }
}
