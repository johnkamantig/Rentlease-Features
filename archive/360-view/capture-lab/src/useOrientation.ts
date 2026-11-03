import { useEffect, useState } from 'react';
import { Accelerometer, Magnetometer } from 'expo-sensors';
import type { OrientationReading, Vector } from './domain';
import { estimateOrientation } from './orientation';

type SensorState = 'checking' | 'available' | 'unavailable' | 'denied' | 'failed';
type Sensor = typeof Accelerometer | typeof Magnetometer;
type Packet = { value: Vector; at: number };

async function check(sensor: Sensor): Promise<SensorState> {
  try {
    if (!await sensor.isAvailableAsync()) return 'unavailable';
    let permission = await sensor.getPermissionsAsync();
    if (!permission.granted && permission.canAskAgain) permission = await sensor.requestPermissionsAsync();
    return permission.granted ? 'available' : 'denied';
  } catch { return 'failed'; }
}

export function useOrientation(enabled: boolean, retry: number) {
  const [reading, setReading] = useState<OrientationReading | null>(null);
  const [availability, setAvailability] = useState<{ acceleration: SensorState; magnetic: SensorState }>({ acceleration: 'checking', magnetic: 'checking' });
  useEffect(() => {
    setReading(null);
    if (!enabled) return;
    let cancelled = false;
    let acceleration: Packet | null = null;
    let magnetic: Packet | null = null;
    const subscriptions: { remove(): void }[] = [];
    setAvailability({ acceleration: 'checking', magnetic: 'checking' });
    const emit = () => {
      if (cancelled) return;
      const now = Date.now();
      if (!acceleration || now - acceleration.at > 1000) { setReading(null); return; }
      const field = magnetic && now - magnetic.at <= 1000 ? magnetic.value : null;
      setReading(estimateOrientation(acceleration.value, field, new Date(acceleration.at).toISOString()));
    };
    void (async () => {
      // Permission prompts are serialized, so two platform dialogs cannot race.
      const accelerationState = await check(Accelerometer);
      const magneticState = await check(Magnetometer);
      if (cancelled) return;
      setAvailability({ acceleration: accelerationState, magnetic: magneticState });
      if (accelerationState === 'available') {
        try {
          Accelerometer.setUpdateInterval(150);
          subscriptions.push(Accelerometer.addListener(value => { acceleration = { value: { x: value.x, y: value.y, z: value.z }, at: Date.now() }; emit(); }));
        } catch { setAvailability(value => ({ ...value, acceleration: 'failed' })); }
      }
      if (magneticState === 'available') {
        try {
          Magnetometer.setUpdateInterval(150);
          subscriptions.push(Magnetometer.addListener(value => { magnetic = { value: { x: value.x, y: value.y, z: value.z }, at: Date.now() }; emit(); }));
        } catch { setAvailability(value => ({ ...value, magnetic: 'failed' })); }
      }
    })();
    const watchdog = setInterval(emit, 500);
    return () => { cancelled = true; subscriptions.forEach(s => s.remove()); clearInterval(watchdog); };
  }, [enabled, retry]);
  return { reading, availability };
}
