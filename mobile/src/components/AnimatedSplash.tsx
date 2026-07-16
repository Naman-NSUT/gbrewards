import React, { useEffect, useState } from 'react';
import { Animated, StyleSheet } from 'react-native';

import { colors } from '../theme';

// Full logo (with tagline) aspect ratio is 1080:201.
const ASPECT = 1080 / 201;
const LOGO_WIDTH = 260;

interface Props {
  onDone: () => void;
}

// Self-contained JS launch splash: logo fades in with a gentle scale, holds,
// then fades out and calls onDone. Uses only the built-in Animated API.
export function AnimatedSplash({ onDone }: Props) {
  const [opacity] = useState(() => new Animated.Value(0));
  const [scale] = useState(() => new Animated.Value(0.9));

  useEffect(() => {
    const animation = Animated.sequence([
      Animated.parallel([
        Animated.timing(opacity, {
          toValue: 1,
          duration: 600,
          useNativeDriver: true,
        }),
        Animated.timing(scale, {
          toValue: 1,
          duration: 700,
          useNativeDriver: true,
        }),
      ]),
      Animated.delay(900),
      Animated.timing(opacity, {
        toValue: 0,
        duration: 450,
        useNativeDriver: true,
      }),
    ]);

    animation.start(({ finished }) => {
      if (finished) onDone();
    });

    return () => animation.stop();
  }, [opacity, scale, onDone]);

  return (
    <Animated.View style={styles.root}>
      <Animated.Image
        source={require('../../assets/logo-full.png')}
        resizeMode="contain"
        style={[
          styles.logo,
          { opacity, transform: [{ scale }] },
        ]}
      />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
  },
  logo: {
    width: LOGO_WIDTH,
    height: LOGO_WIDTH / ASPECT,
  },
});
