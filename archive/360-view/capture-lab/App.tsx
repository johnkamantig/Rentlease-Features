import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { Alert, AppState, BackHandler, FlatList, Image, Linking, Pressable, ScrollView, StatusBar, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { CaptureRepository } from './src/repository';
import { SessionService } from './src/sessionService';
import { nativeFiles, registerCameraTemporary, removeCameraTemporary } from './src/nativeFiles';
import { CAPTURE_BUILD } from './src/cameraCaptures';
import { exportCapture, clearExportCopies } from './src/nativeExport';
import { DIRECTION_LABELS, INSTRUCTIONS, STEPS, SWEEPS, horizontalYaws, isHorizontalSession, nextTarget, progress, type Step, type Sweep, type Target } from './src/domain';
import { angleDelta, freshReading, wrap } from './src/orientation';
import { useOrientation } from './src/useOrientation';

type Screen = 'home' | 'capture' | 'review';
type Reference = { heading: number; setAt: string };

function Button({ title, onPress, disabled = false, secondary = false, danger = false }: {
  title: string; onPress: () => void; disabled?: boolean; secondary?: boolean; danger?: boolean;
}) {
  return <Pressable accessibilityRole="button" accessibilityLabel={title} accessibilityState={{ disabled }}
    disabled={disabled} onPress={onPress}
    style={({ pressed }) => [styles.button, secondary && styles.secondary, danger && styles.danger,
      disabled && styles.disabled, pressed && styles.pressed]}>
    <Text style={[styles.buttonText, secondary && styles.secondaryText]}>{title}</Text>
  </Pressable>;
}

function CaptureLab() {
  const [service] = useState(() => new SessionService(new CaptureRepository(nativeFiles)));
  const state = useSyncExternalStore(service.subscribe, service.getSnapshot);
  const session = state.session;
  const [screen, setScreen] = useState<Screen>('home');
  const [step, setStep] = useState<Step>(20);
  const [sweep, setSweep] = useState<Sweep>(150);
  const horizontal = !!session && isHorizontalSession(session);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [permission, requestPermission, refreshPermission] = useCameraPermissions();
  const [ready, setReady] = useState(false);
  const [cameraKey, setCameraKey] = useState(0);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [uiError, setUiError] = useState<string | null>(null);
  const [foreground, setForeground] = useState(AppState.currentState === 'active');
  const [manual, setManual] = useState(false);
  const [sensorRetry, setSensorRetry] = useState(0);
  const [reference, setReference] = useState<Reference | null>(null);
  const camera = useRef<CameraView>(null);
  const canPreview = screen === 'capture' && foreground && permission?.granted && session?.status === 'active';
  const { reading, availability } = useOrientation(!!canPreview && !manual, sensorRetry);
  const live = freshReading(reading);
  const target = session?.targets.find(t => t.id === selectedId) ?? (session ? nextTarget(session) ?? session.targets[0] : undefined);
  const counts = session ? progress(session) : null;
  const lastPhoto = session?.targets.filter(t => t.photo && t.id !== target?.id && t.direction === target?.direction)
    .sort((a, b) => b.photo!.requestedAt.localeCompare(a.photo!.requestedAt))[0]?.photo;

  useEffect(() => { void service.initialize(); }, [service]);
  useEffect(() => {
    const subscription = AppState.addEventListener('change', value => {
      const active = value === 'active';
      setForeground(active);
      if (!active) { setReady(false); setReference(null); void service.pause(); }
      else void refreshPermission().catch(() => setUiError('Could not recheck camera access. Open phone settings and try again.'));
    });
    return () => subscription.remove();
  }, [service, refreshPermission]);
  useEffect(() => { setReady(false); setCameraError(null); }, [canPreview, cameraKey]);
  useEffect(() => {
    const subscription = BackHandler.addEventListener('hardwareBackPress', () => {
      if (state.busy) return true;
      if (screen === 'capture') { setReference(null); setScreen('review'); void service.pause(); return true; }
      if (screen === 'review') { setScreen('home'); return true; }
      void service.pause();
      return false;
    });
    return () => subscription.remove();
  }, [screen, service, state.busy]);

  async function askCamera() {
    setUiError(null);
    try { await requestPermission(); }
    catch { setUiError('Camera permission could not be requested. Open phone settings and enable Camera for Expo Go.'); }
  }
  async function settings() {
    try { await Linking.openSettings(); }
    catch { setUiError('Open Android Settings, then Apps, Expo Go, Permissions, Camera.'); }
  }
  async function openCapture(id = target?.id) {
    if (AppState.currentState !== 'active') return;
    setUiError(null);
    setReference(null);
    if (id) setSelectedId(id);
    if (await service.resume() && AppState.currentState === 'active') setScreen('capture');
  }
  async function start() {
    if (await service.start(step, sweep)) { setSelectedId(null); setReference(null); setScreen('capture'); }
  }
  async function capture() {
    if (!target || !ready || !canPreview || state.busy || !camera.current) return;
    setUiError(null);
    let temporaryUri: string | undefined;
    const requestedAt = new Date().toISOString();
    const snapshot = manual ? null : freshReading(reading);
    try {
      const success = await service.capture(target.id, async () => {
        const photo = await camera.current!.takePictureAsync({ quality: 0.92, exif: false, skipProcessing: false });
        temporaryUri = photo.uri;
        registerCameraTemporary(photo.uri);
        return photo;
      }, { requestedAt, orientation: snapshot, referenceHeading: reference?.heading ?? null, referenceSetAt: reference?.setAt ?? null });
      if (success) {
        const saved = service.getSnapshot().session!;
        const next = nextTarget(saved, target.id);
        setSelectedId(next?.id ?? target.id);
        if (!next) { setScreen('review'); setReference(null); await service.pause(); }
      }
    } finally { if (temporaryUri) removeCameraTemporary(temporaryUri); }
  }
  async function addOverlap() {
    if (!target || !session) return;
    const index = session.targets.findIndex(t => t.id === target.id);
    if (await service.addExtra(target.id)) {
      const id = service.getSnapshot().session!.targets[index + 1]!.id;
      setSelectedId(id);
      if (screen === 'capture') await openCapture(id);
    }
  }
  function confirmDelete(restart: boolean) {
    Alert.alert(restart ? 'Restart this room capture?' : 'Delete local capture data?',
      'This deletes this prototype’s saved room photos and capture records from this phone. It does not delete your camera roll.', [
        { text: 'Keep photos', style: 'cancel' },
        { text: restart ? 'Delete and restart' : 'Delete photos', style: 'destructive', onPress: () => {
          void (async () => {
            const oldStep = session?.step ?? step;
            const oldSweep = session?.sweepDegrees ?? sweep;
            if (!await service.discard()) return;
            setScreen('home'); setSelectedId(null); setReference(null);
            if (restart && await service.start(oldStep, oldSweep)) setScreen('capture');
          })();
        } },
      ]);
  }

  const yawDelta = target?.yaw !== null && target?.yaw !== undefined && reference && live?.headingDegrees !== null && live?.headingDegrees !== undefined
    ? angleDelta(target.yaw, wrap(live.headingDegrees - reference.heading)) : null;
  const pitchDelta = target && live?.elevationDegrees !== null && live?.elevationDegrees !== undefined
    ? target.elevation - live.elevationDegrees : null;
  const markerX = Math.max(10, Math.min(90, 50 + (yawDelta ?? 0) / 90 * 40));
  const markerY = Math.max(10, Math.min(90, 50 - (pitchDelta ?? 0) / 90 * 40));
  const isBusy = state.busy || !state.initialized;

  const progressPanel = session && counts ? <View style={styles.panel}>
    <Text style={styles.eyebrow}>{session.status === 'complete' ? 'CAPTURE SET SAVED' : 'HORIZONTAL CAPTURE'}</Text>
    <Text style={styles.heading}>{counts.captured} / {counts.planned} guide photos</Text>
    <View accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: counts.planned, now: counts.captured }} style={styles.progressTrack}>
      <View style={[styles.progressFill, { width: `${counts.captured / counts.planned * 100}%` }]} />
    </View>
    <Text style={styles.muted}>Photos saved, not a stitched panorama. Check overlap and add photos where needed.</Text>
  </View> : null;

  return <SafeAreaView style={styles.safe}>
    <StatusBar barStyle="light-content" />
    <View style={styles.header}><View><Text style={styles.brand}>Room panorama capture</Text>
      <Text style={styles.small}>ROOM PHOTOS · ON THIS PHONE ONLY</Text>
      <Text style={styles.small}>Test build: {CAPTURE_BUILD}</Text></View></View>
    {(state.error || uiError || state.notice) && <View style={styles.notice}>
      <Text selectable accessibilityLiveRegion="polite" style={state.error || uiError ? styles.error : styles.body}>{state.error ?? uiError ?? state.notice}</Text>
    </View>}
    {isBusy && <Text accessibilityLiveRegion="polite" style={styles.saving}>Saving or restoring local files… Please wait.</Text>}

    {screen === 'home' && <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>01 / PREPARE THE ROOM</Text>
      <Text style={styles.hero}>Capture a horizontal room view</Text>
      <Text style={styles.body}>Optional capture: turn across part of the room and save overlapping photos. Stitching happens later; no panorama is generated here.</Text>
      {session ? <>{progressPanel}{!horizontal && <Text style={styles.body}>Older full-sphere set: review and export it before starting over. Your photos have not been changed.</Text>}<Button title={!horizontal || session.status === 'complete' ? 'Review saved capture set' : 'Resume saved room capture'} disabled={isBusy}
        onPress={() => { if (!horizontal || session.status === 'complete') setScreen('review'); else void openCapture(nextTarget(session)?.id); }} />
        <Button title="Review photos" secondary disabled={isBusy} onPress={() => setScreen('review')} />
        <Button title="Restart this room" secondary disabled={isBusy} onPress={() => confirmDelete(true)} />
        <Button title="Delete local capture data" danger disabled={isBusy} onPress={() => confirmDelete(false)} /></>
        : <>
          <View style={styles.panel}>
            <Text style={styles.heading}>Before you begin</Text>
            <Text style={styles.body}>1. Choose the left edge of the room view as your starting direction.</Text>
            <Text style={styles.body}>2. Keep the rear lens near one point. Rotate the phone around the lens instead of walking around.</Text>
            <Text style={styles.body}>3. Keep the phone portrait and the same lens/zoom throughout. Hold still for every photo.</Text>
            <Text style={styles.body}>4. Turn right, keeping roughly half of the previous scene visible. Keep the phone level. The guide cannot measure overlap.</Text>
          </View>
          <View style={styles.panel}>
            <Text style={styles.heading}>Planned horizontal sweep</Text>
            <View style={styles.wrap}>{SWEEPS.map(value => <Pressable key={value} accessibilityRole="radio" accessibilityState={{ checked: sweep === value, disabled: isBusy }} disabled={isBusy}
              onPress={() => setSweep(value)} style={[styles.chip, sweep === value && styles.selected]}><Text style={styles.body}>{value}° sweep</Text></Pressable>)}</View>
            <Text style={styles.heading}>Spacing between photos</Text>
            <Text style={styles.muted}>Camera field of view is unknown. Smaller turns give more guide photos; no setting guarantees coverage. If overlap is low, use a denser plan or add photos.</Text>
            <View style={styles.wrap}>{STEPS.map(value => <Pressable key={value} accessibilityRole="radio" accessibilityState={{ checked: step === value, disabled: isBusy }} disabled={isBusy}
              onPress={() => setStep(value)} style={[styles.chip, step === value && styles.selected]}><Text style={styles.body}>{value}° turns</Text></Pressable>)}</View>
            <Text style={styles.small}>{horizontalYaws(step, sweep).length} suggested photos across a {sweep}° turn. Actual coverage depends on the lens and framing. Add overlap photos as needed.</Text>
          </View>
          <Button title="Start room capture" disabled={isBusy || !!state.error} onPress={() => void start()} />
          {state.error && <><Button title="Retry local recovery" secondary disabled={isBusy} onPress={() => void service.initialize()} />
            <Button title="Delete unreadable local capture data" danger disabled={isBusy} onPress={() => confirmDelete(false)} /></>}
        </>}
    </ScrollView>}

    {screen === 'capture' && session && horizontal && target && <>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.heading}>{DIRECTION_LABELS[target.direction]} · Shot {session.targets.indexOf(target) + 1}</Text>
        <Text style={styles.body}>{INSTRUCTIONS[target.direction]}</Text>
        <Text style={styles.muted}>{target.extra ? 'Extra overlap photo: frame a missing area manually.' : `Suggested direction: ${target.yaw === null ? 'straight ' + (target.elevation > 0 ? 'up' : 'down') : target.yaw + '° around from your starting wall'}, tilt ${target.elevation}°.`}</Text>
        <View style={styles.cameraFrame}>
          {canPreview && !cameraError ? <CameraView key={cameraKey} ref={camera} style={StyleSheet.absoluteFill} facing="back" mode="picture" zoom={0} mirror={false}
            onCameraReady={() => setReady(true)} onMountError={() => { setReady(false); setCameraError('The camera preview could not start. Close other camera apps and retry.'); }} />
            : <View style={styles.cameraPlaceholder}><Text style={styles.body}>{cameraError ?? (!permission ? 'Checking camera permission…' : !permission.granted ? 'Camera access is needed for the live preview.' : 'Capture paused. Resume when you are ready.')}</Text></View>}
          {canPreview && ready && !target.extra && <View pointerEvents="none" style={StyleSheet.absoluteFill} accessible={false}>
            <View style={styles.crosshair}><Text style={styles.crosshairText}>＋</Text></View>
            {(yawDelta !== null || pitchDelta !== null) && <View style={[styles.target, { left: `${markerX}%`, top: `${markerY}%` }]} />}
            <View style={styles.cameraCaption}><Text style={styles.captionText}>GUIDE ONLY · MANUAL SHUTTER</Text></View>
          </View>}
        </View>
        {!permission?.granted && <>
          <Text style={styles.muted}>Photos stay in this app’s private storage. Microphone and photo-library access are not needed.</Text>
          <Button title={permission?.canAskAgain === false ? 'Open camera permission settings' : 'Allow camera'} disabled={!permission || isBusy}
            onPress={() => { if (permission?.canAskAgain === false) void settings(); else void askCamera(); }} />
        </>}
        {cameraError && <Button title="Retry camera preview" secondary disabled={isBusy} onPress={() => setCameraKey(value => value + 1)} />}
        {lastPhoto && !target.photo && <View style={styles.photoRow}>
          <Image source={{ uri: service.repository.photoUri(session, lastPhoto) }} style={styles.thumbnail} resizeMethod="resize" accessibilityLabel="Previous photo in this direction for overlap comparison" />
          <View style={styles.flex}><Text style={styles.body}>Keep shared landmarks</Text><Text style={styles.small}>Compare with the last photo in this row. Keep roughly half of the same scene visible. This thumbnail does not measure overlap.</Text></View>
        </View>}
        <View style={styles.panel}>
          <Text style={styles.eyebrow}>APPROXIMATE ORIENTATION</Text>
          <Text style={styles.heading}>{manual ? 'Manual guidance' : `Tilt ${live?.elevationDegrees == null ? '—' : Math.round(live.elevationDegrees) + '°'} · Heading ${live?.headingDegrees == null ? '—' : Math.round(live.headingDegrees) + '°'}`}</Text>
          <Text style={styles.muted}>These readings do not validate camera alignment or overlap. Indoor magnetic fields and movement can make them wrong. Keep the phone level and compare shared landmarks.</Text>
          {!manual && <Text style={styles.small}>Tilt sensor: {availability.acceleration} · Compass sensor: {availability.magnetic}{!live ? ' · No fresh reading; use visual landmarks.' : ''}</Text>}
          {yawDelta !== null && !target.extra && <Text style={styles.body}>Approximate turn: {Math.round(Math.abs(yawDelta))}° {yawDelta >= 0 ? 'clockwise' : 'counterclockwise'} toward the guide.</Text>}
          {!manual && <><Text style={styles.body}>{reference ? 'Starting-wall reference set for this uninterrupted capture.' : 'Face your chosen starting wall, phone upright, then set the reference. Repeat after pause/review or interruption.'}</Text>
            <Button title="Set starting-wall reference" secondary disabled={isBusy || live?.headingDegrees == null || Math.abs(live?.elevationDegrees ?? 90) > 20}
              onPress={() => { if (live?.headingDegrees != null) setReference({ heading: live.headingDegrees, setAt: new Date().toISOString() }); }} />
            <Button title="Retry sensors" secondary disabled={isBusy} onPress={() => { setReference(null); setSensorRetry(n => n + 1); }} /></>}
          <Button title={manual ? 'Enable sensor assistance' : 'Use manual guidance'} secondary disabled={isBusy} onPress={() => { setReference(null); setManual(value => !value); }} />
        </View>
        {target.photo && <View style={styles.panel}><Text style={styles.heading}>Retaking this shot</Text>
          <Image source={{ uri: service.repository.photoUri(session, target.photo) }} style={styles.previous} resizeMode="contain" resizeMethod="resize" accessibilityLabel="Current saved photo for comparison" />
          <Text style={styles.muted}>The current photo stays saved until the replacement is copied and recorded successfully.</Text></View>}
        {progressPanel}
        <Button title="Add an overlap photo here" secondary disabled={isBusy} onPress={() => void addOverlap()} />
      </ScrollView>
      <View style={styles.footer}>
        <Text style={styles.small}>{counts?.captured} / {counts?.planned} guide photos · Check shared landmarks before capturing.</Text>
        {session.status !== 'active' ? <Button title="Resume capture" disabled={isBusy} onPress={() => void openCapture()} />
          : <Button title={state.busy ? 'Saving photo…' : target.photo ? 'Capture replacement photo' : 'Capture photo'} disabled={isBusy || !ready || !canPreview} onPress={() => void capture()} />}
        <View style={styles.row}><View style={styles.flex}><Button title="Pause" secondary disabled={isBusy || session.status !== 'active'} onPress={() => { setReference(null); void service.pause(); }} /></View>
          <View style={styles.flex}><Button title="Review photos" secondary disabled={isBusy} onPress={() => { setReference(null); setScreen('review'); void service.pause(); }} /></View></View>
      </View>
    </>}

    {screen === 'review' && session && <>
      <FlatList data={session.targets} keyExtractor={item => item.id} contentContainerStyle={styles.content}
        ListHeaderComponent={<>{progressPanel}<Text style={styles.heading}>Ordered capture set</Text><Text style={styles.muted}>Select a thumbnail to inspect or retake it. A retake keeps the same position in this list. Empty targets still need a photo.</Text>
          {target?.photo && <View style={styles.panel}>
            <Image source={{ uri: service.repository.photoUri(session, target.photo) }} style={styles.previous} resizeMode="contain" resizeMethod="resize" accessibilityLabel="Selected saved room photograph" />
            <Text style={styles.body}>Shot {session.targets.indexOf(target) + 1} · {target.photo.width} × {target.photo.height} · revision {target.photo.revision}</Text>
            <Text style={styles.small}>Shutter requested: {new Date(target.photo.requestedAt).toLocaleString()}</Text>
            <Text style={styles.small}>Approx. tilt: {target.photo.orientation?.elevationDegrees?.toFixed(0) ?? 'unavailable'} · heading: {target.photo.orientation?.headingDegrees?.toFixed(0) ?? 'unavailable'}</Text>
          </View>}</>}
        renderItem={({ item, index }: { item: Target; index: number }) => <Pressable accessibilityRole="button" accessibilityLabel={`Shot ${index + 1}, ${DIRECTION_LABELS[item.direction]}, ${item.photo ? 'saved' : 'not captured'}`}
          accessibilityState={{ selected: target?.id === item.id, disabled: isBusy }} disabled={isBusy} onPress={() => setSelectedId(item.id)} style={[styles.photoRow, target?.id === item.id && styles.selected]}>
          {item.photo ? <Image source={{ uri: service.repository.photoUri(session, item.photo) }} style={styles.thumbnail} resizeMethod="resize" /> : <View style={[styles.thumbnail, styles.empty]}><Text style={styles.muted}>—</Text></View>}
          <View style={styles.flex}><Text style={styles.body}>{index + 1}. {DIRECTION_LABELS[item.direction]}</Text><Text style={styles.small}>{item.extra ? 'Extra overlap photo' : item.yaw === null ? 'Pole guide' : `${item.yaw}° turn · ${item.elevation}° tilt`}</Text>
            <Text style={styles.small}>{item.photo ? `${item.photo.width} × ${item.photo.height} · saved locally` : 'Not captured'}</Text></View>
        </Pressable>}
        ListFooterComponent={<>
        <Button title="Save original capture ZIP to folder" secondary disabled={isBusy || session.status !== 'complete'} onPress={() => {
          setUiError(null);
          void service.exportSet((set, update) => exportCapture(set, service.repository, 'folder', update));
        }} />
        <Button title="Share original capture ZIP" secondary disabled={isBusy || session.status !== 'complete'} onPress={() => {
          setUiError(null);
          void service.exportSet((set, update) => exportCapture(set, service.repository, 'share', update));
        }} />
        <Button title="Clear temporary export copies" secondary disabled={isBusy} onPress={() => Alert.alert('Clear exported ZIP copies?',
          'Only this app’s cached ZIP files will be removed. Wait for any transfer to finish. Captured originals and copies saved to your chosen folder are kept.',
          [{ text: 'Keep', style: 'cancel' }, { text: 'Clear ZIP copies', onPress: () => {
            try { clearExportCopies(); } catch { setUiError('Some export copies could not be cleared. Retry after the transfer finishes.'); }
          } }])} />
        <Text style={styles.muted}>Export preserves original JPEGs and their metadata. Choose an offline folder, USB, Bluetooth or Quick Share destination. Export does not create a panorama.</Text>
        <Button title="Add an overlap photo after selected shot" secondary disabled={isBusy || !target || !horizontal} onPress={() => void addOverlap()} />
          <Button title="Restart this room" secondary disabled={isBusy} onPress={() => confirmDelete(true)} />
          <Button title="Cancel and delete this set" danger disabled={isBusy} onPress={() => confirmDelete(false)} />
          <Button title="Back to preparation" secondary disabled={isBusy} onPress={() => setScreen('home')} /></>} />
      <View style={styles.footer}>
        <Button title={target?.photo ? 'Retake selected photo' : 'Capture selected target'} disabled={isBusy || !target || !horizontal} onPress={() => void openCapture()} />
        <Button title={session.status === 'complete' ? 'Capture set saved · no panorama yet' : 'Finish and keep capture set'} secondary disabled={isBusy || !!counts?.remaining || session.status === 'complete'} onPress={() => void service.finish()} />

      </View>
    </>}
  </SafeAreaView>;
}

export default function App() { return <SafeAreaProvider><CaptureLab /></SafeAreaProvider>; }

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#181818' },
  header: { paddingHorizontal: 18, paddingVertical: 12, borderBottomWidth: 1, borderColor: '#29423d', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 },
  brand: { color: '#f2f8f4', fontSize: 20, fontWeight: '800' }, lab: { color: '#dddddd', fontWeight: '400' },
  badge: { color: '#a3c2b5', borderColor: '#47645b', borderWidth: 1, borderRadius: 5, padding: 5, fontSize: 9, letterSpacing: 1 },
  content: { padding: 18, gap: 14, paddingBottom: 28 },
  hero: { color: '#f2f8f4', fontSize: 22, fontWeight: '600', lineHeight: 28 },
  heading: { color: '#eff7f2', fontSize: 20, fontWeight: '700', lineHeight: 27 },
  eyebrow: { color: '#dddddd', fontSize: 11, fontWeight: '700', letterSpacing: 1.5 },
  body: { color: '#e1eee7', fontSize: 15, lineHeight: 22 },
  muted: { color: '#b3c9be', fontSize: 13, lineHeight: 20 },
  small: { color: '#adc6ba', fontSize: 11, lineHeight: 17 },
  panel: { backgroundColor: '#242424', borderColor: '#315246', borderWidth: 1, borderRadius: 4, padding: 16, gap: 10 },
  button: { minHeight: 48, backgroundColor: '#dddddd', paddingVertical: 13, paddingHorizontal: 14, borderRadius: 4, alignItems: 'center', justifyContent: 'center', marginVertical: 4 },
  buttonText: { color: '#10271a', fontSize: 15, fontWeight: '700', textAlign: 'center' },
  secondary: { backgroundColor: '#203a31', borderWidth: 1, borderColor: '#52705e' },
  secondaryText: { color: '#e2f0e6' }, danger: { backgroundColor: '#efb1a1' },
  disabled: { opacity: 0.45 }, pressed: { opacity: 0.7 },
  chip: { minHeight: 44, borderRadius: 9, borderWidth: 1, borderColor: '#456354', paddingHorizontal: 12, paddingVertical: 10, backgroundColor: '#182e27' },
  selected: { borderColor: '#a3eec5', borderWidth: 2, backgroundColor: '#294a3c' },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, row: { flexDirection: 'row', gap: 8 }, flex: { flex: 1 },
  progressTrack: { height: 6, backgroundColor: '#345145', borderRadius: 3, overflow: 'hidden' }, progressFill: { height: 6, backgroundColor: '#a1e8bb' },
  cameraFrame: { height: 340, borderRadius: 4, overflow: 'hidden', backgroundColor: '#050b09', borderColor: '#476255', borderWidth: 1 },
  cameraPlaceholder: { flex: 1, padding: 25, alignItems: 'center', justifyContent: 'center' },
  crosshair: { position: 'absolute', left: '50%', top: '50%', transform: [{ translateX: -20 }, { translateY: -25 }] },
  crosshairText: { color: '#fff', fontSize: 40, textShadowColor: '#000', textShadowRadius: 4 },
  target: { position: 'absolute', width: 40, height: 40, borderWidth: 3, borderColor: '#ffdb8b', borderRadius: 20, transform: [{ translateX: -20 }, { translateY: -20 }] },
  cameraCaption: { position: 'absolute', bottom: 10, alignSelf: 'center', backgroundColor: '#0d1918df', borderRadius: 5, padding: 7 },
  captionText: { color: '#f8edcd', fontSize: 10, letterSpacing: 1 },
  footer: { borderTopWidth: 1, borderColor: '#355043', backgroundColor: '#13261f', padding: 12, gap: 2 },
  notice: { backgroundColor: '#2d392b', padding: 12 }, error: { color: '#ffcbba', fontSize: 14, lineHeight: 20 },
  saving: { color: '#c6eccf', padding: 9, fontSize: 12 },
  thumbnail: { width: 78, height: 78, borderRadius: 7 }, previous: { width: '100%', height: 190, borderRadius: 8, backgroundColor: '#080f0c' },
  photoRow: { borderWidth: 1, borderColor: '#355246', borderRadius: 4, padding: 10, flexDirection: 'row', gap: 12, marginVertical: 4, alignItems: 'center' },
  empty: { backgroundColor: '#1c3228', alignItems: 'center', justifyContent: 'center' },
});
