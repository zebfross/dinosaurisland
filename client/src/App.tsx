import { Routes, Route, Navigate } from 'react-router-dom';
import { useGameStore } from './state/gameStore';
import { LoginScreen } from './components/lobby/LoginScreen';
import { LobbyView } from './components/lobby/LobbyView';
import { GameView } from './components/game/GameView';

function App() {
  const { token } = useGameStore();

  if (!token) {
    return <LoginScreen />;
  }

  return (
    <Routes>
      <Route path="/" element={<LobbyView />} />
      <Route path="/game/:gameId" element={<GameView />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
