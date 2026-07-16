import React from 'react';
import { Image } from 'react-native';

// Wordmark aspect ratio is 720:103. Default height 26 => width ~182.
const ASPECT = 720 / 103;

interface Props {
  height?: number;
}

export function AppLogo({ height = 26 }: Props) {
  return (
    <Image
      source={require('../../assets/logo-wordmark.png')}
      resizeMode="contain"
      style={{ height, width: height * ASPECT }}
    />
  );
}
