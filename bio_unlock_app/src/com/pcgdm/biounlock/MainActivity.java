package com.pcgdm.biounlock;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.hardware.biometrics.BiometricPrompt;
import android.hardware.fingerprint.FingerprintManager;
import android.os.Build;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.view.Gravity;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.lang.reflect.Method;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

public class MainActivity extends Activity {
    private static final String DEFAULT_PC_MAC = "A4:D1:8C:62:0B:25";
    private static final String DEFAULT_PC_IP = "10.1.0.82";
    private static final int TCP_PORT = 29422;
    private static final int UDP_DISCOVERY_PORT = 29423;
    private static final int RFCOMM_CHANNEL = 22;
    private static final String SECRET_HEX = "afec2608476dde798028c9dab7b9064e8c5e1987517623073969f6b1f05ec0c6";
    private static final String PREFS = "pcgdm_biounlock";
    private static final String KEY_MAC = "pc_mac";
    private static final String KEY_IP = "pc_ip";

    private TextView statusView;
    private TextView targetView;
    private volatile InputStream activeIn;
    private volatile OutputStream activeOut;
    private volatile Runnable activeCloser;
    private volatile String activeNonce;
    private volatile String lastError;
    private volatile String transportLabel;
    private volatile CountDownLatch challengeLatch;
    private CancellationSignal cancelSignal;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setPadding(64, 64, 64, 64);
        root.setBackgroundColor(Color.parseColor("#0D1117"));

        ImageView logo = new ImageView(this);
        logo.setImageResource(R.drawable.logo);
        LinearLayout.LayoutParams logoLp = new LinearLayout.LayoutParams(240, 240);
        logoLp.bottomMargin = 32;
        logo.setLayoutParams(logoLp);
        root.addView(logo);

        TextView title = new TextView(this);
        title.setText("PC Bio-Unlock");
        title.setTextColor(Color.WHITE);
        title.setTextSize(28f);
        title.setTypeface(null, Typeface.BOLD);
        title.setGravity(Gravity.CENTER);
        root.addView(title);

        targetView = new TextView(this);
        targetView.setTextColor(Color.parseColor("#8B949E"));
        targetView.setTextSize(14f);
        targetView.setGravity(Gravity.CENTER);
        targetView.setPadding(0, 16, 0, 48);
        root.addView(targetView);

        statusView = new TextView(this);
        statusView.setText("Touch rear fingerprint sensor...");
        statusView.setTextColor(Color.parseColor("#58A6FF"));
        statusView.setTextSize(18f);
        statusView.setGravity(Gravity.CENTER);
        statusView.setPadding(0, 24, 0, 64);
        root.addView(statusView);

        Button unlockBtn = new Button(this);
        unlockBtn.setText("Scan Fingerprint & Unlock");
        unlockBtn.setTextColor(Color.WHITE);
        unlockBtn.setBackgroundColor(Color.parseColor("#238636"));
        unlockBtn.setPadding(40, 28, 40, 28);
        unlockBtn.setOnClickListener(v -> startUnlockFlow());
        root.addView(unlockBtn);

        Button pickBtn = new Button(this);
        pickBtn.setText("Select Paired PC (BT)");
        pickBtn.setTextColor(Color.parseColor("#C9D1D9"));
        pickBtn.setBackgroundColor(Color.parseColor("#21262D"));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        lp.topMargin = 32;
        pickBtn.setLayoutParams(lp);
        pickBtn.setOnClickListener(v -> showDevicePicker());
        root.addView(pickBtn);

        setContentView(root);
        updateTargetLabel();
        startUnlockFlow();
    }

    private String getTargetMac() {
        return getSharedPreferences(PREFS, MODE_PRIVATE).getString(KEY_MAC, DEFAULT_PC_MAC);
    }

    private String getTargetIp() {
        return getSharedPreferences(PREFS, MODE_PRIVATE).getString(KEY_IP, DEFAULT_PC_IP);
    }

    private void updateTargetLabel() {
        targetView.setText("PC: " + getTargetIp() + ":" + TCP_PORT + " | BT: " + getTargetMac());
    }

    private void showDevicePicker() {
        if (Build.VERSION.SDK_INT >= 31 &&
                checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.BLUETOOTH_CONNECT}, 101);
            return;
        }
        BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
        if (adapter == null) {
            setStatus("Bluetooth not available", "#F85149");
            return;
        }
        Set<BluetoothDevice> bonded = adapter.getBondedDevices();
        List<BluetoothDevice> list = new ArrayList<>(bonded);
        String[] names = new String[list.size()];
        for (int i = 0; i < list.size(); i++) {
            names[i] = list.get(i).getName() + " (" + list.get(i).getAddress() + ")";
        }
        new AlertDialog.Builder(this)
                .setTitle("Select Paired PC")
                .setItems(names, (d, which) -> {
                    getSharedPreferences(PREFS, MODE_PRIVATE)
                            .edit()
                            .putString(KEY_MAC, list.get(which).getAddress())
                            .apply();
                    updateTargetLabel();
                    startUnlockFlow();
                })
                .show();
    }

    private void startUnlockFlow() {
        closeActive();
        activeNonce = null;
        lastError = null;
        transportLabel = null;
        challengeLatch = new CountDownLatch(1);
        setStatus("Connecting & waiting for fingerprint...", "#58A6FF");

        new Thread(this::connectAndReadChallenge).start();
        promptFingerprint();
    }

    private String discoverLanIp() {
        try (DatagramSocket ds = new DatagramSocket()) {
            ds.setBroadcast(true);
            ds.setSoTimeout(500);
            byte[] req = "PCGDM_DISCOVER".getBytes(StandardCharsets.US_ASCII);
            ds.send(new DatagramPacket(req, req.length, InetAddress.getByName("255.255.255.255"), UDP_DISCOVERY_PORT));
            byte[] buf = new byte[128];
            DatagramPacket resp = new DatagramPacket(buf, buf.length);
            ds.receive(resp);
            String msg = new String(resp.getData(), 0, resp.getLength(), StandardCharsets.US_ASCII).trim();
            if (msg.startsWith("PCGDM_HERE:")) {
                String ip = resp.getAddress().getHostAddress();
                getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(KEY_IP, ip).apply();
                runOnUiThread(this::updateTargetLabel);
                return ip;
            }
        } catch (Exception ignored) {
        }
        return null;
    }

    private boolean tryTcpConnect(String host, int timeoutMs, String label) {
        Socket s = null;
        try {
            s = new Socket();
            s.connect(new InetSocketAddress(host, TCP_PORT), timeoutMs);
            s.setSoTimeout(5000);
            InputStream in = s.getInputStream();
            OutputStream out = s.getOutputStream();
            BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.US_ASCII));
            String line = reader.readLine();
            if (line != null && line.startsWith("CHALLENGE:")) {
                activeNonce = line.substring("CHALLENGE:".length()).trim();
                activeIn = in;
                activeOut = out;
                Socket finalSock = s;
                activeCloser = () -> {
                    try { finalSock.close(); } catch (Exception ignored) {}
                };
                transportLabel = label;
                return true;
            }
            s.close();
        } catch (Exception e) {
            lastError = label + " failed: " + e.getMessage();
            if (s != null) {
                try { s.close(); } catch (Exception ignored) {}
            }
        }
        return false;
    }

    private boolean tryBluetoothConnect() {
        try {
            if (Build.VERSION.SDK_INT >= 31 &&
                    checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
                return false;
            }
            BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
            if (adapter == null || !adapter.isEnabled()) {
                return false;
            }
            BluetoothDevice dev = adapter.getRemoteDevice(getTargetMac());
            Method m = dev.getClass().getMethod("createRfcommSocket", int.class);
            BluetoothSocket sock = (BluetoothSocket) m.invoke(dev, RFCOMM_CHANNEL);
            sock.connect();

            InputStream in = sock.getInputStream();
            OutputStream out = sock.getOutputStream();
            BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.US_ASCII));
            String line = reader.readLine();
            if (line != null && line.startsWith("CHALLENGE:")) {
                activeNonce = line.substring("CHALLENGE:".length()).trim();
                activeIn = in;
                activeOut = out;
                activeCloser = () -> {
                    try { sock.close(); } catch (Exception ignored) {}
                };
                transportLabel = "Bluetooth";
                return true;
            }
            sock.close();
        } catch (Exception e) {
            lastError = "BT failed: " + e.getMessage();
        }
        return false;
    }

    private void connectAndReadChallenge() {
        try {
            if (tryBluetoothConnect()) {
                setStatus("Connected via Bluetooth — scan finger!", "#3FB950");
                return;
            }

            Set<String> hosts = new LinkedHashSet<>();
            hosts.add("127.0.0.1"); // USB adb reverse
            hosts.add(getTargetIp());
            hosts.add(DEFAULT_PC_IP);

            for (String h : hosts) {
                int timeout = "127.0.0.1".equals(h) ? 200 : 450;
                String lbl = "127.0.0.1".equals(h) ? "USB" : "Wi-Fi (" + h + ")";
                if (tryTcpConnect(h, timeout, lbl)) {
                    setStatus("Connected via " + transportLabel + " — scan finger!", "#3FB950");
                    return;
                }
            }

            String discovered = discoverLanIp();
            if (discovered != null && tryTcpConnect(discovered, 600, "Wi-Fi (" + discovered + ")")) {
                setStatus("Connected via " + transportLabel + " — scan finger!", "#3FB950");
                return;
            }

            setStatus(lastError != null ? lastError : "PC not reachable", "#F85149");
        } finally {
            challengeLatch.countDown();
        }
    }

    private void promptFingerprint() {
        if (cancelSignal != null) cancelSignal.cancel();
        cancelSignal = new CancellationSignal();

        if (Build.VERSION.SDK_INT >= 28) {
            BiometricPrompt prompt = new BiometricPrompt.Builder(this)
                    .setTitle("Unlock Librarianist PC")
                    .setSubtitle("Touch rear fingerprint sensor")
                    .setNegativeButton("Cancel", getMainExecutor(), (d, w) -> setStatus("Cancelled", "#8B949E"))
                    .build();
            prompt.authenticate(cancelSignal, getMainExecutor(), new BiometricPrompt.AuthenticationCallback() {
                @Override
                public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult result) {
                    onFingerprintVerified();
                }

                @Override
                public void onAuthenticationError(int errorCode, CharSequence errString) {
                    setStatus("Auth error: " + errString, "#F85149");
                }
            });
        } else {
            FingerprintManager fm = (FingerprintManager) getSystemService(FINGERPRINT_SERVICE);
            if (fm == null || !fm.isHardwareDetected() || !fm.hasEnrolledFingerprints()) {
                setStatus("No fingerprint enrolled", "#F85149");
                return;
            }
            fm.authenticate(null, cancelSignal, 0, new FingerprintManager.AuthenticationCallback() {
                @Override
                public void onAuthenticationSucceeded(FingerprintManager.AuthenticationResult result) {
                    onFingerprintVerified();
                }

                @Override
                public void onAuthenticationError(int errMsgId, CharSequence errString) {
                    setStatus("Auth error: " + errString, "#F85149");
                }
            }, null);
        }
    }

    private void onFingerprintVerified() {
        setStatus("Fingerprint matched! Unlocking PC...", "#D29922");
        new Thread(() -> {
            try {
                challengeLatch.await(4, TimeUnit.SECONDS);
                if (activeOut == null || activeIn == null || activeNonce == null) {
                    setStatus(lastError != null ? lastError : "Not connected to PC", "#F85149");
                    return;
                }
                String sig = hmacSha256(hexToBytes(SECRET_HEX), activeNonce);
                activeOut.write(("AUTH:" + sig + "\n").getBytes(StandardCharsets.US_ASCII));
                activeOut.flush();

                BufferedReader reader = new BufferedReader(new InputStreamReader(activeIn, StandardCharsets.US_ASCII));
                String reply = reader.readLine();
                if ("OK".equals(reply)) {
                    setStatus("PC UNLOCKED! (" + transportLabel + ")", "#3FB950");
                } else {
                    setStatus("PC rejected auth: " + reply, "#F85149");
                }
            } catch (Exception e) {
                setStatus("Unlock error: " + e.getMessage(), "#F85149");
            } finally {
                closeActive();
            }
        }).start();
    }

    private static String hmacSha256(byte[] key, String msg) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(key, "HmacSHA256"));
        byte[] raw = mac.doFinal(msg.getBytes(StandardCharsets.US_ASCII));
        StringBuilder sb = new StringBuilder(raw.length * 2);
        for (byte b : raw) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }

    private static byte[] hexToBytes(String s) {
        byte[] out = new byte[s.length() / 2];
        for (int i = 0; i < out.length; i++) {
            out[i] = (byte) Integer.parseInt(s.substring(i * 2, i * 2 + 2), 16);
        }
        return out;
    }

    private void setStatus(String text, String hexColor) {
        runOnUiThread(() -> {
            statusView.setText(text);
            statusView.setTextColor(Color.parseColor(hexColor));
        });
    }

    private void closeActive() {
        if (activeCloser != null) {
            activeCloser.run();
            activeCloser = null;
        }
        activeIn = null;
        activeOut = null;
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (cancelSignal != null) cancelSignal.cancel();
        closeActive();
    }
}
