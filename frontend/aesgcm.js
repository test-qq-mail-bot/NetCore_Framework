/* aesgcm.js - 纯 JS 实现的 AES-256-GCM（不依赖 Web Crypto / crypto.subtle）
 *
 * 目的：前端登录时对用户名/密码做 AES-256-GCM 加密，与后端 core.crypto_utils.CryptoUtils 完全兼容。
 * 兼容性原则：
 *   - 密钥：Base64 解码后 32 字节（AES-256）
 *   - 随机 12 字节 IV（nonce）
 *   - 输出 = Base64( IV(12) || 密文 || 认证标签(16) )，与后端 CryptoUtils.encrypt 的输出布局一致
 *   - 不依赖 crypto.subtle，因此在任何上下文（localhost / 127.0.0.1 / 局域网 IP / 非安全上下文）都能工作
 *
 * 该实现用于会话级凭证加密，属“纵深防御”性质，不能替代 HTTPS。
 * 密钥说明（原注释“后端每次随机生成且仅存于内存”与实现不符，已更正）：
 *   后端以 config/core.yaml 的 crypto.encryption_key（主密钥）为根，
 *   经 HMAC-SHA256 派生出独立的「传输子密钥」，由公开接口 /api/system/crypto-key
 *   下发（审查修复：不再直接下发主密钥，防止其被用于解密落盘敏感字段）。
 */
(function (global) {
    "use strict";

    // ---------------- AES S-box ----------------
    const SBOX = [
        0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
        0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
        0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
        0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
        0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
        0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
        0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
        0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
        0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
        0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
        0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
        0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
        0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
        0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
        0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
        0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
    ];

    // ---------------- 基础工具 ----------------
    function xtime(a) {
        let r = (a << 1) & 0xff;
        if (a & 0x80) r ^= 0x1b;
        return r & 0xff;
    }
    function gmul(a, b) {
        let p = 0;
        for (let i = 0; i < 8; i++) {
            if (b & 1) p ^= a;
            const hi = a & 0x80;
            a = (a << 1) & 0xff;
            if (hi) a ^= 0x1b;
            b >>= 1;
        }
        return p & 0xff;
    }
    function xorBytes(a, b) {
        const out = new Uint8Array(a.length);
        for (let i = 0; i < a.length; i++) out[i] = a[i] ^ b[i];
        return out;
    }
    function base64ToBytes(b64) {
        const bin = (typeof atob === "function") ? atob(b64) : Buffer.from(b64, "base64").toString("binary");
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        return bytes;
    }
    function bytesToBase64(bytes) {
        let bin = "";
        for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
        return (typeof btoa === "function") ? btoa(bin) : Buffer.from(bin, "binary").toString("base64");
    }

    // ---------------- AES 密钥扩展（AES-256）----------------
    function subWord(w) {
        return (SBOX[(w >>> 24) & 0xff] << 24) | (SBOX[(w >>> 16) & 0xff] << 16) |
               (SBOX[(w >>> 8) & 0xff] << 8) | SBOX[w & 0xff];
    }
    function rotWord(w) {
        return ((w << 8) | (w >>> 24)) >>> 0;
    }
    function keyExpansion(key) {
        // key: Uint8Array(32)
        const Nk = 8, Nr = 14;
        const w = [];
        for (let i = 0; i < Nk; i++) {
            w.push((key[4 * i] << 24) | (key[4 * i + 1] << 16) | (key[4 * i + 2] << 8) | key[4 * i + 3]);
        }
        const Rcon = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36];
        for (let i = Nk; i < 4 * (Nr + 1); i++) {
            let temp = w[i - 1];
            if (i % Nk === 0) {
                temp = subWord(rotWord(temp)) ^ (Rcon[(i / Nk) - 1] << 24);
            } else if (Nk > 6 && i % Nk === 4) {
                temp = subWord(temp);
            }
            w.push((w[i - Nk] ^ temp) >>> 0);
        }
        const rk = [];
        for (let r = 0; r < Nr + 1; r++) {
            const block = new Uint8Array(16);
            for (let b = 0; b < 4; b++) {
                const word = w[r * 4 + b] >>> 0;
                block[b * 4 + 0] = (word >>> 24) & 0xff;
                block[b * 4 + 1] = (word >>> 16) & 0xff;
                block[b * 4 + 2] = (word >>> 8) & 0xff;
                block[b * 4 + 3] = word & 0xff;
            }
            rk.push(block);
        }
        return rk;
    }

    // ---------------- AES 单块加密 ----------------
    function addRoundKey(state, rk) {
        for (let i = 0; i < 16; i++) state[i] ^= rk[i];
    }
    function subBytes(state) {
        for (let i = 0; i < 16; i++) state[i] = SBOX[state[i]];
    }
    function shiftRows(state) {
        const t = state.slice();
        for (let r = 0; r < 4; r++) {
            for (let c = 0; c < 4; c++) {
                state[r + 4 * c] = t[r + 4 * ((c + r) % 4)];
            }
        }
    }
    function mixColumns(state) {
        for (let c = 0; c < 4; c++) {
            const i = 4 * c;
            const a0 = state[i], a1 = state[i + 1], a2 = state[i + 2], a3 = state[i + 3];
            state[i]     = gmul(a0, 2) ^ gmul(a1, 3) ^ a2 ^ a3;
            state[i + 1] = a0 ^ gmul(a1, 2) ^ gmul(a2, 3) ^ a3;
            state[i + 2] = a0 ^ a1 ^ gmul(a2, 2) ^ gmul(a3, 3);
            state[i + 3] = gmul(a0, 3) ^ a1 ^ a2 ^ gmul(a3, 2);
        }
    }
    function aesEncryptBlock(input, rk) {
        const Nr = rk.length - 1;
        const state = input.slice();
        addRoundKey(state, rk[0]);
        for (let round = 1; round < Nr; round++) {
            subBytes(state);
            shiftRows(state);
            mixColumns(state);
            addRoundKey(state, rk[round]);
        }
        subBytes(state);
        shiftRows(state);
        addRoundKey(state, rk[Nr]);
        return state;
    }

    // ---------------- GHASH ----------------
    const R = new Uint8Array([0xe1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
    function gfMult(x, y) {
        const z = new Uint8Array(16);
        const v = y.slice();
        for (let i = 0; i < 128; i++) {
            const bit = (x[i >> 3] >> (7 - (i & 7))) & 1;
            if (bit) {
                for (let j = 0; j < 16; j++) z[j] ^= v[j];
            }
            const lsb = v[15] & 1;
            // 右移一位
            let carry = 0;
            for (let j = 0; j < 16; j++) {
                const nb = (v[j] >> 1) | (carry << 7);
                carry = v[j] & 1;
                v[j] = nb;
            }
            if (lsb) {
                for (let j = 0; j < 16; j++) v[j] ^= R[j];
            }
        }
        return z;
    }
    function ghash(H, ciphertext, aad) {
        let Y = new Uint8Array(16);
        const blocks = [aad, ciphertext];
        for (const data of blocks) {
            for (let off = 0; off < data.length; off += 16) {
                const block = new Uint8Array(16);
                for (let i = 0; i < 16 && off + i < data.length; i++) block[i] = data[off + i];
                Y = gfMult(xorBytes(Y, block), H);
            }
        }
        // 长度块：len(AAD) 与 len(C) 各 64 位（比特数，大端）
        const lenBlock = new Uint8Array(16);
        let aadBits = aad.length * 8;
        let cBits = ciphertext.length * 8;
        // 写入 64 位大端
        for (let i = 7; i >= 0; i--) { lenBlock[i] = aadBits & 0xff; aadBits >>>= 8; }
        for (let i = 15; i >= 8; i--) { lenBlock[i] = cBits & 0xff; cBits >>>= 8; }
        Y = gfMult(xorBytes(Y, lenBlock), H);
        return Y;
    }

    // ---------------- CTR 模式 ----------------
    function inc32(block) {
        for (let i = 15; i >= 12; i--) {
            if (block[i] === 0xff) { block[i] = 0; }
            else { block[i]++; break; }
        }
    }
    function ctrEncrypt(pt, encKey, iv) {
        const ct = new Uint8Array(pt.length);
        const counter = new Uint8Array(16);
        counter.set(iv);
        counter[15] = 2; // 第一个计数器块 = J0 + 1 = iv || 0x00000002
        let pos = 0;
        while (pos < pt.length) {
            const ks = aesEncryptBlock(counter, encKey);
            const n = Math.min(16, pt.length - pos);
            for (let i = 0; i < n; i++) ct[pos + i] = pt[pos + i] ^ ks[i];
            pos += n;
            inc32(counter);
        }
        return ct;
    }

    // ---------------- 对外：AES-256-GCM 加密 ----------------
    function aesGcmEncrypt(plaintext, keyB64) {
        const key = base64ToBytes(keyB64);
        const encKey = keyExpansion(key);
        // IV(nonce) 必须不可预测且绝不能在同一密钥下重复：
        // Math.random() 不是密码学安全随机源，且周期短、可被预测，一旦 IV 重复
        // GCM 的密钥流就会复用。因此优先使用 crypto.getRandomValues，
        // 仅在极旧环境（无 crypto 对象）才退回 Math.random 兜底。
        const iv = new Uint8Array(12);
        const cryptoObj = (typeof crypto !== "undefined" && crypto) ||
            (typeof globalThis !== "undefined" && globalThis.crypto) || null;
        if (cryptoObj && typeof cryptoObj.getRandomValues === "function") {
            cryptoObj.getRandomValues(iv);
        } else {
            for (let i = 0; i < 12; i++) iv[i] = Math.floor(Math.random() * 256);
        }
        const pt = (typeof TextEncoder !== "undefined")
            ? new TextEncoder().encode(plaintext)
            : new Uint8Array(Buffer.from(plaintext, "utf-8"));
        const ciphertext = ctrEncrypt(pt, encKey, iv);
        // H = E_K(0^128)
        const H = aesEncryptBlock(new Uint8Array(16), encKey);
        const Y = ghash(H, ciphertext, new Uint8Array(0));
        // J0 = iv || 0x00000001
        const J0 = new Uint8Array(16);
        J0.set(iv);
        J0[15] = 1;
        const S = aesEncryptBlock(J0, encKey);
        const tag = xorBytes(Y, S);
        const out = new Uint8Array(12 + ciphertext.length + 16);
        out.set(iv, 0);
        out.set(ciphertext, 12);
        out.set(tag, 12 + ciphertext.length);
        return bytesToBase64(out);
    }

    // 暴露到全局（浏览器）或 module.exports（Node 测试）
    global.aesGcmEncrypt = aesGcmEncrypt;
    if (typeof module !== "undefined" && module.exports) {
        module.exports = { aesGcmEncrypt: aesGcmEncrypt };
    }
})(typeof window !== "undefined" ? window : (typeof globalThis !== "undefined" ? globalThis : this));
