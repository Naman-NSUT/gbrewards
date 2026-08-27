/** Jest config for the dealer Expo app (jest-expo preset). */
module.exports = {
  preset: 'jest-expo',
  transformIgnorePatterns: [
    'node_modules/(?!((jest-)?react-native|@react-native(-community)?|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@tanstack/.*|axios))',
  ],
  testMatch: ['**/*.test.ts', '**/*.test.tsx'],
};
