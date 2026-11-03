import { useEffect, useRef, useState } from 'react';
import { Button, Image, Platform, ScrollView, Text, View } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { DeviceMotion, Gyroscope } from 'expo-sensors';
import * as Sharing from 'expo-sharing';
import { isStitchingAvailable, stitchImagePaths } from '@notchip/expo-panoramic-stitcher';
import { useGuidedSweep } from '@notchip/expo-panoramic-stitcher/capture';
import { evaluateCapture } from './session';

export default function App() {
  const [permission, requestPermission] = useCameraPermissions();
  const [sensorReady, setSensorReady] = useState(false);
  const [status, setStatus] = useState('Checking motion sensor...');
  const [busy, setBusy] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [capture, setCapture] = useState(true);
  const [outcome, setOutcome] = useState<Awaited<ReturnType<typeof evaluateCapture>> | null>(null);
  const handled = useRef<string | null>(null);
  const sweep = useGuidedSweep({ stepDeg: 15, maxShots: 26, photoQuality: 0.9, exif: true, haptics: false });
  const available = Platform.OS === 'android' && isStitchingAvailable();
  useEffect(() => { void (async () => {
    try {
      const [motion, gyro] = await Promise.all([DeviceMotion.isAvailableAsync(),Gyroscope.isAvailableAsync()]);
      const present = motion && gyro;
      const p = await DeviceMotion.requestPermissionsAsync();
      setSensorReady(present && p.granted);
      setStatus(present && p.granted ? 'Ready. Hold phone upright and level before Start.' : 'Motion sensor unavailable or permission denied.');
    } catch(e) { setStatus(String(e)); }
  })(); }, []);
  useEffect(() => {
    if (sweep.phase !== 'done' || !sweep.meta || handled.current === sweep.meta.id) return;
    handled.current = sweep.meta.id;
    setBusy(true); setCapture(false);
    void evaluateCapture(sweep.shots, sweep.meta, setStatus).then(result => {
      setOutcome(result); setStatus('Finished. Diagnostic output only; no accepted 360 export.');
    }).catch(error => setStatus(String(error))).finally(() => setBusy(false));
  }, [sweep.phase, sweep.meta, sweep.shots]);
  if (!available) return <View style={{flex:1,padding:30,justifyContent:'center'}}>
    <Text>Android native build required. This module is unavailable in Expo Go or on web.</Text>
  </View>;
  if (!permission?.granted) return <View style={{flex:1,padding:30,justifyContent:'center'}}>
    <Text>Camera permission is required. Audio is not recorded.</Text>
    <Button title="Grant camera permission" onPress={() => void requestPermission()} />
  </View>;
  return <View style={{flex:1,paddingTop:35,paddingBottom:24,backgroundColor:'#fff'}}>
    <Text style={{fontSize:20,padding:10}}>RentLease sweep experiment</Text>
    {capture && <CameraView style={{width:'100%',aspectRatio:3/4}} facing="back" zoom={0}
      ref={sweep.cameraRef} onCameraReady={() => { setCameraReady(true); sweep.onCameraReady(); }}
      onMountError={e => setStatus(`Camera error: ${e.message}`)} />}
    <ScrollView contentContainerStyle={{padding:12,gap:10}}>
      <Text>{status}</Text>
      {capture && <>
        <Text>Estimated rotation: {Math.min(360,Math.round(Math.abs(sweep.hud.yawDeg)))} / 360 degrees. {sweep.shots.length} photos.</Text>
        <Text>{sweep.hud.status.replaceAll('_',' ')} | Tilt {sweep.hud.tiltDeg.toFixed(1)} | Roll {sweep.hud.rollDeg.toFixed(1)}</Text>
        <Text>Rotate slowly in one direction about the camera. Pause when prompted. Finish after returning to the starting scene at 360 degrees. No ceiling or floor row.</Text>
        {sweep.phase === 'sweeping'
          ? <Button title="Finish" disabled={sweep.hud.status === 'HOLD'} onPress={sweep.finish}/>
          : <Button title="Start" disabled={!sensorReady || !cameraReady || !sweep.isCameraReady || busy} onPress={sweep.start}/>}
        <Text>Wait for the final photo count to update before Finish; Finish pauses while the capture guidance says HOLD.</Text>
      </>}
      {outcome && <>
        <Text selectable>Saved session: {outcome.directory}</Text>
        <Text selectable>{JSON.stringify({ error:outcome.report.error, stitchMs:outcome.report.stitchMs,
          bytes:outcome.report.bytes, inspection:outcome.report.inspection },null,2)}</Text>
        {outcome.preview && <><Text>Flat diagnostic preview. This is not a verified 360 viewer.</Text>
          <Image source={{uri:outcome.preview}} style={{width:'100%',height:160}} resizeMode="contain"/></>}
        <Button title="Share diagnostic JSON" onPress={() => void Sharing.shareAsync(outcome.uri,{mimeType:'application/json'}).catch(e=>setStatus(String(e)))}/>
      </>}
      {!capture && !busy && <Button title="Retry (keeps saved session)" onPress={() => {
        sweep.reset(); setOutcome(null); setCameraReady(false); setCapture(true); setStatus('Ready for another sweep.');
      }}/>}
      {sweep.phase !== 'sweeping' && !busy && <Button title="Test unreadable image error" onPress={() => {
        setBusy(true);
        void stitchImagePaths(['/notchip-missing-a.jpg','/notchip-missing-b.jpg'],{autoResize:false}).then(
          () => setStatus('FAILED negative test: unreadable images resolved unexpectedly.'),
          e => setStatus(`Unreadable-image rejection observed: ${String(e)}`),
        ).finally(()=>setBusy(false));
      }}/>}
    </ScrollView>
  </View>;
}
