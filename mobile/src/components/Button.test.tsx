import { fireEvent, render, screen } from '@testing-library/react-native';

import { Button } from './Button';

describe('Button', () => {
  it('renders its title and fires onPress', () => {
    const onPress = jest.fn();
    render(<Button title="Tap me" onPress={onPress} />);
    fireEvent.press(screen.getByText('Tap me'));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('does not fire onPress while loading', () => {
    const onPress = jest.fn();
    render(<Button title="Saving" onPress={onPress} loading />);
    // While loading the label is replaced by a spinner.
    expect(screen.queryByText('Saving')).toBeNull();
  });

  it('does not fire onPress when disabled', () => {
    const onPress = jest.fn();
    render(<Button title="Nope" onPress={onPress} disabled />);
    fireEvent.press(screen.getByText('Nope'));
    expect(onPress).not.toHaveBeenCalled();
  });
});
